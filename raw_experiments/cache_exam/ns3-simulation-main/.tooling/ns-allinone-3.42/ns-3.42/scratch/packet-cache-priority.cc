/*
 * Packet/chunk cache-priority experiment.
 *
 * The application uses UDP only.  There is no transport-layer retransmission.
 * Each stream keeps its configured Mbps production rate and emits transport
 * chunks no larger than its configured payload size. Packets are the cache
 * units. The point-to-point device supplies the bottleneck
 * rate and the receiver-side RateErrorModel supplies independent loss.
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/error-model.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/udp-socket-factory.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

namespace
{

constexpr double DEFAULT_LINK_UPDATE_SECONDS = 1.0;
constexpr double MB = 1000000.0;
constexpr double DEFAULT_CACHE_CAPACITY_MB = 50.0;
constexpr uint32_t NETWORK_OVERHEAD_BYTES = 80;
constexpr uint32_t HEADER_MAGIC = 0x50434c31; // PCL1
constexpr double EPSILON = 1e-6;
constexpr double AGING_ALPHA_PROM = 1.7;
constexpr double UTILITY_NUM_RECEIVERS = 1.0;
constexpr std::size_t VIDEO_STREAM_INDEX = 4;
constexpr std::size_t IMAGE_STREAM_INDEX = 5;
constexpr std::size_t STREAM_COUNT = 6;
const double UTILITY_MAX_DELAY_SECONDS[] = {120.0, 300.0, 1.0, 1800.0, 2.0, 5.0};

enum class Strategy
{
    FIFO,
    SP,
    AGING,
    MAXF,
    UTILITY,
    UTILITY_TI,
    NO_CACHE
};

constexpr double MAXF_ZIPF_THETA = 1.5;
// Stream vector order is D1,D2,D3,D4,V1,I1; Zipf ranks are D3,D4,D1,D2,I1,V1.
constexpr uint32_t MAXF_ZIPF_RANK[STREAM_COUNT] = {3, 4, 1, 2, 6, 5};

struct LinkSample
{
    double timeMin;
    double capacityMbps;
    double rttMs;
    double lossRate;
};

LinkSample InterpolateSample(const std::vector<LinkSample>& samples, double absoluteMin)
{
    if (absoluteMin <= samples.front().timeMin)
    {
        return samples.front();
    }
    if (absoluteMin >= samples.back().timeMin)
    {
        return samples.back();
    }
    for (std::size_t i = 1; i < samples.size(); ++i)
    {
        if (absoluteMin <= samples[i].timeMin)
        {
            const auto& left = samples[i - 1];
            const auto& right = samples[i];
            double fraction = (absoluteMin - left.timeMin) /
                              (right.timeMin - left.timeMin);
            return {
                absoluteMin,
                left.capacityMbps + fraction * (right.capacityMbps - left.capacityMbps),
                left.rttMs + fraction * (right.rttMs - left.rttMs),
                left.lossRate + fraction * (right.lossRate - left.lossRate),
            };
        }
    }
    return samples.back();
}

struct StreamSpec
{
    std::string id;
    double rateMbps;
    int priorityLevel;
    double priorityWeight;
    double ttlSeconds;
    bool key;
};

const std::vector<StreamSpec> STREAMS = {
    {"D1", 0.000010133, 2, 2.0, 600.0, false},
    {"D2", 0.000005733, 2, 2.0, 600.0, false},
    {"D3", 0.010240, 1, 3.0, 300.0, true},
    {"D4", 0.000013880, 1, 3.0, 300.0, true},
    {"V1", 1.667848, 3, 1.0, 1800.0, false},
    {"I1", 0.413944, 2, 2.0, 600.0, false},
};

struct Metrics
{
    double produced = 0.0;
    double cacheEvicted = 0.0;
    double sourceDropped = 0.0;
    double sent = 0.0;
    double delivered = 0.0;
    double pending = 0.0;
};

struct Chunk
{
    uint64_t id;
    uint32_t stream;
    uint32_t originalBytes;
    uint32_t remainingBytes;
    double createdSeconds;
    bool eventFlag;
    int currentPriority;
    double lastAgingSeconds;
    uint64_t queueOrder;
    bool active = true;
};

struct Checkpoint
{
    double timeSeconds;
    std::vector<Metrics> metrics;
    std::vector<double> pending;
    double peakCacheBytes;
};

class ChunkHeader : public Header
{
  public:
    ChunkHeader() = default;
    ChunkHeader(uint32_t stream, uint64_t chunk, uint32_t payload)
        : m_stream(stream),
          m_chunk(static_cast<uint32_t>(chunk)),
          m_payload(payload)
    {
    }

    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("ns3::PacketCacheChunkHeader")
                                .SetParent<Header>()
                                .SetGroupName("Applications")
                                .AddConstructor<ChunkHeader>();
        return tid;
    }

    TypeId GetInstanceTypeId() const override
    {
        return GetTypeId();
    }

    void Print(std::ostream& os) const override
    {
        os << "stream=" << m_stream << " chunk=" << m_chunk << " payload=" << m_payload;
    }

    uint32_t GetSerializedSize() const override
    {
        return 16;
    }

    void Serialize(Buffer::Iterator start) const override
    {
        start.WriteHtonU32(HEADER_MAGIC);
        start.WriteHtonU32(m_stream);
        start.WriteHtonU32(m_chunk);
        start.WriteHtonU32(m_payload);
    }

    uint32_t Deserialize(Buffer::Iterator start) override
    {
        uint32_t magic = start.ReadNtohU32();
        if (magic != HEADER_MAGIC)
        {
            return 0;
        }
        m_stream = start.ReadNtohU32();
        m_chunk = start.ReadNtohU32();
        m_payload = start.ReadNtohU32();
        return 16;
    }

    uint32_t GetStream() const
    {
        return m_stream;
    }

    uint32_t GetPayload() const
    {
        return m_payload;
    }

  private:
    uint32_t m_stream = 0;
    uint32_t m_chunk = 0;
    uint32_t m_payload = 0;
};

NS_OBJECT_ENSURE_REGISTERED(ChunkHeader);

class ReceiverApplication : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("ns3::PacketCacheReceiver")
                                .SetParent<Application>()
                                .SetGroupName("Applications")
                                .AddConstructor<ReceiverApplication>();
        return tid;
    }

    void SetMetrics(std::vector<Metrics>* metrics)
    {
        m_metrics = metrics;
    }

  private:
    void StartApplication() override
    {
        m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        InetSocketAddress local(Ipv4Address::GetAny(), 9000);
        m_socket->Bind(local);
        m_socket->SetRecvCallback(MakeCallback(&ReceiverApplication::Receive, this));
    }

    void StopApplication() override
    {
        if (m_socket)
        {
            m_socket->Close();
        }
    }

    void Receive(Ptr<Socket> socket)
    {
        Address from;
        while (Ptr<Packet> packet = socket->RecvFrom(from))
        {
            ChunkHeader header;
            if (packet->PeekHeader(header) == 0)
            {
                continue;
            }
            packet->RemoveHeader(header);
            if (m_metrics && header.GetStream() < m_metrics->size())
            {
                (*m_metrics)[header.GetStream()].delivered += header.GetPayload();
            }
        }
    }

    Ptr<Socket> m_socket;
    std::vector<Metrics>* m_metrics = nullptr;
};

NS_OBJECT_ENSURE_REGISTERED(ReceiverApplication);

class CacheApplication : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("ns3::PacketCacheSource")
                                .SetParent<Application>()
                                .SetGroupName("Applications")
                                .AddConstructor<CacheApplication>();
        return tid;
    }

    void Configure(Ptr<Socket> socket,
                   Ipv4Address destination,
                   const std::vector<LinkSample>& samples,
                   Strategy strategy,
                   std::vector<Metrics>* metrics,
                   double duration,
                   bool noCache,
                   double startMin,
                   double linkUpdateSeconds,
                   const std::vector<uint32_t>& recordBytes,
                   const std::vector<uint32_t>& packetBytes,
                   const std::vector<double>& ratesMbps,
                   double cacheCapacityMb)
    {
        m_socket = socket;
        m_destination = InetSocketAddress(destination, 9000);
        m_samples = samples;
        m_strategy = strategy;
        m_metrics = metrics;
        m_duration = duration;
        m_noCache = noCache;
        m_startMin = startMin;
        m_recordBytes = recordBytes;
        m_packetBytes = packetBytes;
        m_ratesMbps = ratesMbps;
        m_cacheCapacityBytes = cacheCapacityMb * MB;
        m_generationRemainingBytes.assign(STREAMS.size(), 0);
        // Only cached strategies own an application-layer cache queue.  The
        // no-cache baseline sends each generated packet immediately and never
        // inserts it into this queue. Reserve enough elements for the current
        // run so pointers stored in the auxiliary queues remain stable even
        // when the image record size is large.
        if (!m_noCache)
        {
            std::size_t estimatedChunks = 0;
            for (std::size_t stream = 0; stream < STREAMS.size(); ++stream)
            {
                if (stream == VIDEO_STREAM_INDEX || stream == IMAGE_STREAM_INDEX)
                {
                    double recordPeriod =
                        (static_cast<double>(m_recordBytes[stream]) * 8.0) /
                        (m_ratesMbps[stream] * 1000000.0);
                    std::size_t recordCount =
                        static_cast<std::size_t>(std::ceil(m_duration / recordPeriod));
                    std::size_t chunksPerRecord =
                        (m_recordBytes[stream] + m_packetBytes[stream] - 1) /
                        m_packetBytes[stream];
                    estimatedChunks += recordCount * chunksPerRecord + 2;
                }
                else
                {
                    double bytesPerSecond = m_ratesMbps[stream] * 1000000.0 / 8.0;
                    estimatedChunks += static_cast<std::size_t>(
                        std::ceil((m_duration * bytesPerSecond) /
                                  static_cast<double>(m_packetBytes[stream]))) +
                                      2;
                }
            }
            m_appCache.reserve(estimatedChunks);
        }
    }

    double GetPeakCacheBytes() const
    {
        return m_peakCacheBytes;
    }

  private:
    void StartApplication() override
    {
        m_socket->Bind();
        m_socket->Connect(m_destination);
        for (std::size_t stream = 0; stream < STREAMS.size(); ++stream)
        {
            Simulator::ScheduleNow(&CacheApplication::GeneratePacket, this, stream);
        }
        if (m_duration > 23.5 * 60.0 + EPSILON)
        {
            Simulator::Schedule(Seconds(23.5 * 60.0), &CacheApplication::CaptureCheckpoint, this);
        }
        if (m_duration > 42.0 * 60.0 + EPSILON)
        {
            Simulator::Schedule(Seconds(42.0 * 60.0), &CacheApplication::CaptureCheckpoint, this);
        }
        Simulator::Schedule(Seconds(m_duration), &CacheApplication::SnapshotPending, this);
    }

    void StopApplication() override
    {
        if (m_socket)
        {
            m_socket->Close();
        }
    }

    void GeneratePacket(std::size_t stream)
    {
        double now = Simulator::Now().GetSeconds();
        if (stream >= STREAMS.size() || now >= m_duration)
        {
            return;
        }

        // Video and image records are packetized at generation time. Their
        // configured Mbps rate determines the record period, so 1472-byte
        // chunks arrive evenly across that period (about 20.89 s for V1, 5 s for I1).
        uint32_t generatedBytes = m_recordBytes[stream];
        if (stream == VIDEO_STREAM_INDEX || stream == IMAGE_STREAM_INDEX)
        {
            if (m_generationRemainingBytes[stream] == 0)
            {
                m_generationRemainingBytes[stream] = m_recordBytes[stream];
            }
            generatedBytes = std::min(m_packetBytes[stream], m_generationRemainingBytes[stream]);
            m_generationRemainingBytes[stream] -= generatedBytes;
        }

        uint64_t chunkId = m_nextChunkId++;
        (*m_metrics)[stream].produced += generatedBytes;

        double generationInterval =
            (static_cast<double>(generatedBytes) * 8.0) /
            (m_ratesMbps[stream] * 1000000.0);
        Simulator::Schedule(Seconds(generationInterval),
                            &CacheApplication::GeneratePacket,
                            this,
                            stream);

        // A zero-capacity cache still attempts immediate transmission. Do not
        // enqueue and evict the packet before the sender gets a chance to use
        // the link; failed immediate sends at zero capacity count as evictions.
        if (m_noCache || m_cacheCapacityBytes <= EPSILON)
        {
            TrySendImmediately(stream, chunkId, generatedBytes, now);
            return;
        }

        Chunk chunk;
        chunk.id = chunkId;
        chunk.stream = static_cast<uint32_t>(stream);
        chunk.originalBytes = generatedBytes;
        chunk.remainingBytes = generatedBytes;
        chunk.createdSeconds = now;
        chunk.eventFlag = EventFlag(stream, now);
        chunk.currentPriority = STREAMS[stream].priorityLevel;
        chunk.lastAgingSeconds = now;
        chunk.queueOrder = m_nextQueueOrder++;
        m_appCache.push_back(chunk);
        Chunk* stored = &m_appCache.back();
        m_insertionQueue.push_back(stored);
        m_streamQueues[stream].push_back(stored);
        m_priorityQueues[chunk.currentPriority].push_back(stored);
        m_activeCacheBytes += generatedBytes;
        ++m_activeChunkCount;
        m_agingTimestampSum += now;

        EvictIfNeeded(now);
        UpdatePeakCache();
        if (!m_sendScheduled)
        {
            m_sendScheduled = true;
            Simulator::ScheduleNow(&CacheApplication::SendNext, this);
        }
    }

    void TrySendImmediately(std::size_t stream,
                            uint64_t chunkId,
                            uint32_t payloadBytes,
                            double now)
    {
        // No-Cache has no application-layer queue and no retry path.  The
        // application-level serializer represents whether the bottleneck can
        // accept a packet at this instant.  If it is busy, the packet is
        // dropped at the source instead of being retained anywhere here.
        const bool zeroCapacityCache = !m_noCache && m_cacheCapacityBytes <= EPSILON;
        if (now + EPSILON < m_nextAvailableSendSeconds)
        {
            if (zeroCapacityCache)
            {
                (*m_metrics)[stream].cacheEvicted += payloadBytes;
            }
            else
            {
                (*m_metrics)[stream].sourceDropped += payloadBytes;
            }
            return;
        }

        Ptr<Packet> packet = Create<Packet>(payloadBytes);
        packet->AddHeader(ChunkHeader(stream, chunkId, payloadBytes));
        int result = m_socket->Send(packet);
        uint32_t wireBytes = payloadBytes + ChunkHeader().GetSerializedSize();
        if (result < 0 || static_cast<uint32_t>(result) < wireBytes)
        {
            if (zeroCapacityCache)
            {
                (*m_metrics)[stream].cacheEvicted += payloadBytes;
            }
            else
            {
                (*m_metrics)[stream].sourceDropped += payloadBytes;
            }
            return;
        }

        (*m_metrics)[stream].sent += payloadBytes;
        LinkSample sample = InterpolateSample(m_samples, m_startMin + now / 60.0);
        double interval =
            (static_cast<double>(payloadBytes + NETWORK_OVERHEAD_BYTES) * 8.0) /
            (sample.capacityMbps * 1000000.0);
        m_nextAvailableSendSeconds = now + std::max(interval, 0.000001);
    }

    static bool EventFlag(std::size_t stream, double now)
    {
        double minute = now / 60.0;
        return (stream == 2 && minute >= 14.0 && minute < 20.0) ||
               (stream == 3 && minute >= 16.0 && minute < 22.0);
    }

    double Freshness(const Chunk& chunk, double now) const
    {
        double age = std::max(0.0, now - chunk.createdSeconds);
        return std::max(0.0, 1.0 - age / STREAMS[chunk.stream].ttlSeconds);
    }

    double Score(const Chunk& chunk, double now) const
    {
        const auto& spec = STREAMS[chunk.stream];
        switch (m_strategy)
        {
        case Strategy::FIFO:
            return -chunk.createdSeconds - static_cast<double>(chunk.id) * 1e-12;
        case Strategy::SP:
            return spec.priorityWeight * 1000000.0 - chunk.createdSeconds -
                   static_cast<double>(chunk.id) * 1e-12;
        case Strategy::AGING:
            return static_cast<double>(4 - chunk.currentPriority) * 1000000.0 -
                   static_cast<double>(chunk.queueOrder) * 1e-6;
        case Strategy::MAXF:
        {
            // MaxF: M_i = w_i / (1 + rho_i), rho_i = lambda_i / mu_i.
            // Rates and record sizes come from the experiment report.
            double weight = ZipfWeight(chunk.stream);
            double capacityMbps = CurrentCapacityMbps(now);
            double arrivalRate = m_ratesMbps[chunk.stream] * 1000000.0 /
                                  (8.0 * m_recordBytes[chunk.stream]);
            double serviceRate = capacityMbps * 1000000.0 /
                                  (8.0 * m_recordBytes[chunk.stream]);
            double load = serviceRate > EPSILON
                              ? arrivalRate / serviceRate
                              : std::numeric_limits<double>::infinity();
            return weight / (1.0 + load) - static_cast<double>(chunk.id) * 1e-12;
        }
        case Strategy::UTILITY:
        case Strategy::UTILITY_TI:
        {
            double delaySeconds = UTILITY_MAX_DELAY_SECONDS[chunk.stream];
            if (m_strategy == Strategy::UTILITY_TI)
            {
                // T_i is the configured generation period of the original
                // record, not the 1472-byte transport-chunk interval used by
                // V1 and I1.
                delaySeconds =
                    (static_cast<double>(m_recordBytes[chunk.stream]) * 8.0) /
                    (m_ratesMbps[chunk.stream] * 1000000.0);
            }
            return (UTILITY_NUM_RECEIVERS /
                    (delaySeconds * static_cast<double>(m_packetBytes[chunk.stream]))) *
                       1e9 -
                   static_cast<double>(chunk.id) * 1e-12;
        }
        case Strategy::NO_CACHE:
            return -static_cast<double>(chunk.id);
        }
        return 0.0;
    }

    double CurrentCapacityMbps(double now) const
    {
        return InterpolateSample(m_samples, m_startMin + now / 60.0).capacityMbps;
    }

    double ZipfWeight(std::size_t stream) const
    {
        double denominator = 0.0;
        for (std::size_t index = 0; index < STREAMS.size(); ++index)
        {
            denominator += 1.0 / std::pow(static_cast<double>(index + 1), MAXF_ZIPF_THETA);
        }
        return (1.0 / std::pow(static_cast<double>(MAXF_ZIPF_RANK[stream]), MAXF_ZIPF_THETA)) /
               denominator;
    }

    void ApplyAging(double now)
    {
        if (m_strategy != Strategy::AGING || m_activeChunkCount == 0)
        {
            return;
        }

        double averageWaitingTime =
            std::max(0.0, now - m_agingTimestampSum / static_cast<double>(m_activeChunkCount));
        double agingThreshold = AGING_ALPHA_PROM * averageWaitingTime;

        for (int priority = 3; priority >= 2; --priority)
        {
            CleanPriorityQueue(priority);
            while (!m_priorityQueues[priority].empty())
            {
                Chunk* chunk = m_priorityQueues[priority].front();
                double waitingTime = std::max(0.0, now - chunk->lastAgingSeconds);
                if (waitingTime <= agingThreshold)
                {
                    break;
                }
                m_priorityQueues[priority].pop_front();
                // P3 -> P2 -> P1; promotion enters the new queue at its tail.
                --chunk->currentPriority;
                m_agingTimestampSum += now - chunk->lastAgingSeconds;
                chunk->lastAgingSeconds = now;
                chunk->queueOrder = m_nextQueueOrder++;
                m_priorityQueues[chunk->currentPriority].push_back(chunk);
            }
        }
    }

    std::size_t BestChunk(double now)
    {
        ApplyAging(now);
        if (m_strategy == Strategy::FIFO || m_strategy == Strategy::NO_CACHE)
        {
            while (!m_insertionQueue.empty() && !m_insertionQueue.front()->active)
            {
                m_insertionQueue.pop_front();
            }
            return IndexOf(m_insertionQueue.front());
        }
        if (m_strategy == Strategy::SP)
        {
            for (int priority = 1; priority <= 3; ++priority)
            {
                CleanPriorityQueue(priority);
                if (!m_priorityQueues[priority].empty())
                {
                    return IndexOf(m_priorityQueues[priority].front());
                }
            }
        }
        if (m_strategy == Strategy::AGING)
        {
            for (int priority = 1; priority <= 3; ++priority)
            {
                CleanPriorityQueue(priority);
                if (!m_priorityQueues[priority].empty())
                {
                    return IndexOf(m_priorityQueues[priority].front());
                }
            }
        }
        if (m_strategy == Strategy::MAXF || m_strategy == Strategy::UTILITY ||
            m_strategy == Strategy::UTILITY_TI)
        {
            Chunk* best = nullptr;
            for (std::size_t stream = 0; stream < STREAMS.size(); ++stream)
            {
                CleanStreamQueue(stream);
                if (m_streamQueues[stream].empty())
                {
                    continue;
                }
                Chunk* candidate = m_streamQueues[stream].front();
                if (!best || Score(*candidate, now) > Score(*best, now))
                {
                    best = candidate;
                }
            }
            if (best)
            {
                return IndexOf(best);
            }
        }
        return IndexOf(m_insertionQueue.front());
    }

    std::size_t WorstChunk(double now)
    {
        ApplyAging(now);
        if (m_strategy == Strategy::FIFO || m_strategy == Strategy::NO_CACHE)
        {
            // FIFO service with drop-tail overflow: discard the newest active chunk.
            while (!m_insertionQueue.empty() && !m_insertionQueue.back()->active)
            {
                m_insertionQueue.pop_back();
            }
            return IndexOf(m_insertionQueue.back());
        }
        if (m_strategy == Strategy::SP || m_strategy == Strategy::AGING)
        {
            int first = m_strategy == Strategy::SP ? 3 : 3;
            int last = m_strategy == Strategy::SP ? 1 : 1;
            int step = -1;
            for (int priority = first; priority != last + step; priority += step)
            {
                CleanPriorityQueue(priority);
                if (!m_priorityQueues[priority].empty())
                {
                    return IndexOf(m_priorityQueues[priority].back());
                }
            }
        }
        if (m_strategy == Strategy::MAXF || m_strategy == Strategy::UTILITY ||
            m_strategy == Strategy::UTILITY_TI)
        {
            Chunk* worst = nullptr;
            for (std::size_t stream = 0; stream < STREAMS.size(); ++stream)
            {
                CleanStreamQueue(stream);
                if (m_streamQueues[stream].empty())
                {
                    continue;
                }
                Chunk* candidate = m_streamQueues[stream].back();
                if (!worst || Score(*candidate, now) < Score(*worst, now))
                {
                    worst = candidate;
                }
            }
            if (worst)
            {
                return IndexOf(worst);
            }
        }
        return IndexOf(m_insertionQueue.back());
    }

    double CacheBytes() const
    {
        return m_activeCacheBytes;
    }

    std::size_t IndexOf(const Chunk* chunk) const
    {
        return static_cast<std::size_t>(chunk - m_appCache.data());
    }

    void CleanStreamQueue(std::size_t stream)
    {
        auto& queue = m_streamQueues[stream];
        while (!queue.empty() && !queue.front()->active)
        {
            queue.pop_front();
        }
        while (!queue.empty() && !queue.back()->active)
        {
            queue.pop_back();
        }
    }

    void CleanPriorityQueue(int priority)
    {
        auto& queue = m_priorityQueues[priority];
        while (!queue.empty() &&
               (!queue.front()->active || queue.front()->currentPriority != priority))
        {
            queue.pop_front();
        }
        while (!queue.empty() &&
               (!queue.back()->active || queue.back()->currentPriority != priority))
        {
            queue.pop_back();
        }
    }

    void Deactivate(Chunk& chunk)
    {
        if (!chunk.active)
        {
            return;
        }
        chunk.active = false;
        m_activeCacheBytes -= chunk.remainingBytes;
        m_agingTimestampSum -= chunk.lastAgingSeconds;
        --m_activeChunkCount;
    }

    void EvictIfNeeded(double now)
    {
        if (m_noCache)
        {
            return;
        }
        while (CacheBytes() > m_cacheCapacityBytes + EPSILON && m_activeChunkCount > 0)
        {
            std::size_t index = WorstChunk(now);
            double bytes = m_appCache[index].remainingBytes;
            (*m_metrics)[m_appCache[index].stream].cacheEvicted += bytes;
            Deactivate(m_appCache[index]);
        }
        UpdatePeakCache();
    }

    void UpdatePeakCache()
    {
        m_peakCacheBytes = std::max(m_peakCacheBytes, CacheBytes());
    }

    void SendNext()
    {
        m_sendScheduled = false;
        double now = Simulator::Now().GetSeconds();
        if (now >= m_duration || m_activeChunkCount == 0)
        {
            return;
        }

        std::size_t index = BestChunk(now);
        Chunk& chunk = m_appCache[index];
        uint32_t bytes = std::min(m_packetBytes[chunk.stream], chunk.remainingBytes);
        Ptr<Packet> packet = Create<Packet>(bytes);
        packet->AddHeader(ChunkHeader(chunk.stream, chunk.id, bytes));
        int result = m_socket->Send(packet);
        if (result < 0)
        {
            m_sendScheduled = true;
            Simulator::Schedule(MilliSeconds(1), &CacheApplication::SendNext, this);
            return;
        }

        chunk.remainingBytes -= bytes;
        m_activeCacheBytes -= bytes;
        (*m_metrics)[chunk.stream].sent += bytes;
        if (chunk.remainingBytes == 0)
        {
            Deactivate(chunk);
        }
        UpdatePeakCache();

        LinkSample sample = InterpolateSample(m_samples, m_startMin + now / 60.0);
        double interval = (static_cast<double>(bytes + NETWORK_OVERHEAD_BYTES) * 8.0) /
                          (sample.capacityMbps * 1000000.0);
        m_sendScheduled = true;
        Simulator::Schedule(Seconds(std::max(interval, 0.000001)), &CacheApplication::SendNext, this);

    }

    void SnapshotPending()
    {
        if (m_snapshotTaken)
        {
            return;
        }
        m_snapshotTaken = true;
        for (const auto& chunk : m_appCache)
        {
            if (!chunk.active)
            {
                continue;
            }
            m_metricsSnapshot[chunk.stream] += chunk.remainingBytes;
        }
        CaptureCheckpoint();
    }

    void CaptureCheckpoint()
    {
        double now = Simulator::Now().GetSeconds();
        if (!m_checkpoints.empty() &&
            std::abs(m_checkpoints.back().timeSeconds - now) < EPSILON)
        {
            return;
        }
        std::vector<double> pending(STREAMS.size(), 0.0);
        for (const auto& chunk : m_appCache)
        {
            if (chunk.active)
            {
                pending[chunk.stream] += chunk.remainingBytes;
            }
        }
        m_checkpoints.push_back({now, *m_metrics, pending, m_peakCacheBytes});
    }

  public:
    std::vector<double> GetPendingSnapshot() const
    {
        return m_metricsSnapshot;
    }

    const std::vector<Checkpoint>& GetCheckpoints() const
    {
        return m_checkpoints;
    }

  private:
    Ptr<Socket> m_socket;
    Address m_destination;
    std::vector<LinkSample> m_samples;
    Strategy m_strategy = Strategy::FIFO;
    std::vector<Metrics>* m_metrics = nullptr;
    double m_duration = 0.0;
    bool m_noCache = false;
    bool m_sendScheduled = false;
    bool m_snapshotTaken = false;
    double m_startMin = 0.0;
    uint64_t m_nextChunkId = 1;
    uint64_t m_nextQueueOrder = 1;
    double m_peakCacheBytes = 0.0;
    double m_activeCacheBytes = 0.0;
    double m_cacheCapacityBytes = DEFAULT_CACHE_CAPACITY_MB * MB;
    double m_nextAvailableSendSeconds = 0.0;
    double m_agingTimestampSum = 0.0;
    std::size_t m_activeChunkCount = 0;
    std::vector<Chunk> m_appCache;
    std::deque<Chunk*> m_insertionQueue;
    std::deque<Chunk*> m_streamQueues[STREAM_COUNT];
    std::deque<Chunk*> m_priorityQueues[4];
    std::vector<uint32_t> m_recordBytes = {76, 43, 128, 1041, 4354778, 258715};
    std::vector<uint32_t> m_packetBytes = {76, 43, 128, 1041, 1472, 1472};
    std::vector<double> m_ratesMbps = {0.000050665, 0.000028665, 0.051200, 0.000069400, 1.667848, 0.413944};
    std::vector<uint32_t> m_generationRemainingBytes = std::vector<uint32_t>(STREAMS.size(), 0);
    std::vector<double> m_metricsSnapshot = std::vector<double>(STREAMS.size(), 0.0);
    std::vector<Checkpoint> m_checkpoints;
};

NS_OBJECT_ENSURE_REGISTERED(CacheApplication);

std::string Trim(const std::string& value)
{
    std::size_t first = value.find_first_not_of(" \t\r\n");
    std::size_t last = value.find_last_not_of(" \t\r\n");
    if (first == std::string::npos)
    {
        return "";
    }
    return value.substr(first, last - first + 1);
}

std::vector<LinkSample> ReadSamples(const std::string& path, double startMin, double endMin)
{
    std::ifstream input(path);
    if (!input)
    {
        NS_FATAL_ERROR("Cannot open link CSV: " << path);
    }
    std::string line;
    std::getline(input, line);
    std::vector<LinkSample> samples;
    while (std::getline(input, line))
    {
        std::stringstream ss(line);
        std::string field;
        std::vector<std::string> fields;
        while (std::getline(ss, field, ','))
        {
            fields.push_back(Trim(field));
        }
        if (fields.size() < 5)
        {
            continue;
        }
        double timeMin = std::stod(fields[0]);
        if (timeMin + EPSILON < startMin || timeMin > endMin + EPSILON)
        {
            continue;
        }
        samples.push_back({timeMin, std::stod(fields[2]), std::stod(fields[3]), std::stod(fields[4])});
    }
    if (samples.empty())
    {
        NS_FATAL_ERROR("No link samples selected from CSV");
    }
    return samples;
}

Strategy ParseStrategy(const std::string& value)
{
    if (value == "FIFO") return Strategy::FIFO;
    if (value == "Priority-SP") return Strategy::SP;
    if (value == "Priority-Aging") return Strategy::AGING;
    if (value == "Priority-MaxF") return Strategy::MAXF;
    if (value == "Priority-Utility") return Strategy::UTILITY;
    if (value == "Priority-Utility-Ti") return Strategy::UTILITY_TI;
    if (value == "No-Cache") return Strategy::NO_CACHE;
    NS_FATAL_ERROR("Unknown strategy: " << value);
    return Strategy::FIFO;
}

void WriteResults(const std::string& path,
                  const std::string& stateId,
                  const std::string& strategyName,
                  const std::vector<Metrics>& metrics,
                  const std::vector<double>& pendingSnapshot,
                  double peakCacheBytes,
                  const std::vector<Checkpoint>& checkpoints,
                  uint64_t seed)
{
    std::ofstream output(path);
    if (!output)
    {
        NS_FATAL_ERROR("Cannot write output: " << path);
    }
    output << "record_type,state_id,strategy,stream_id,checkpoint_time_min,produced_mb,cache_evicted_mb,source_dropped_mb,sent_mb,delivered_mb,link_dropped_mb,pending_mb,peak_cache_mb,seed\n";
    double totalProduced = 0.0;
    double totalCache = 0.0;
    double totalSource = 0.0;
    double totalSent = 0.0;
    double totalDelivered = 0.0;
    double totalPending = 0.0;
    for (std::size_t i = 0; i < metrics.size(); ++i)
    {
        totalProduced += metrics[i].produced;
        totalCache += metrics[i].cacheEvicted;
        totalSource += metrics[i].sourceDropped;
        totalSent += metrics[i].sent;
        totalDelivered += metrics[i].delivered;
        totalPending += pendingSnapshot[i];
    }
    output << std::fixed << std::setprecision(9);
    output << "summary," << stateId << "," << strategyName << ",ALL,," << totalProduced / MB << ","
           << totalCache / MB << "," << totalSource / MB << "," << totalSent / MB << ","
           << totalDelivered / MB << "," << (totalSent - totalDelivered) / MB << ","
           << totalPending / MB << "," << peakCacheBytes / MB << "," << seed << "\n";
    for (std::size_t i = 0; i < metrics.size(); ++i)
    {
        output << "stream," << stateId << "," << strategyName << "," << STREAMS[i].id << ",,"
               << metrics[i].produced / MB << "," << metrics[i].cacheEvicted / MB << ","
               << metrics[i].sourceDropped / MB << "," << metrics[i].sent / MB << ","
               << metrics[i].delivered / MB << "," << (metrics[i].sent - metrics[i].delivered) / MB
               << "," << pendingSnapshot[i] / MB << "," << peakCacheBytes / MB << "," << seed << "\n";
    }

    for (const auto& checkpoint : checkpoints)
    {
        std::string checkpointState = checkpoint.timeSeconds <= 23.5 * 60.0 + EPSILON
                                          ? "S1"
                                          : (checkpoint.timeSeconds <= 42.0 * 60.0 + EPSILON ? "S2" : "S3");
        double totalCheckpointProduced = 0.0;
        double totalCheckpointCache = 0.0;
        double totalCheckpointSource = 0.0;
        double totalCheckpointSent = 0.0;
        double totalCheckpointDelivered = 0.0;
        double totalCheckpointPending = 0.0;
        for (std::size_t i = 0; i < checkpoint.metrics.size(); ++i)
        {
            totalCheckpointProduced += checkpoint.metrics[i].produced;
            totalCheckpointCache += checkpoint.metrics[i].cacheEvicted;
            totalCheckpointSource += checkpoint.metrics[i].sourceDropped;
            totalCheckpointSent += checkpoint.metrics[i].sent;
            totalCheckpointDelivered += checkpoint.metrics[i].delivered;
            totalCheckpointPending += checkpoint.pending[i];
        }
        output << "checkpoint_summary," << checkpointState << "," << strategyName << ",ALL,"
               << checkpoint.timeSeconds / 60.0 << "," << totalCheckpointProduced / MB << ","
               << totalCheckpointCache / MB << "," << totalCheckpointSource / MB << ","
               << totalCheckpointSent / MB << "," << totalCheckpointDelivered / MB << ","
               << (totalCheckpointSent - totalCheckpointDelivered) / MB << ","
               << totalCheckpointPending / MB << "," << checkpoint.peakCacheBytes / MB << "," << seed << "\n";
        for (std::size_t i = 0; i < checkpoint.metrics.size(); ++i)
        {
            output << "checkpoint_stream," << checkpointState << "," << strategyName << ","
                   << STREAMS[i].id << "," << checkpoint.timeSeconds / 60.0 << ","
                   << checkpoint.metrics[i].produced / MB << ","
                   << checkpoint.metrics[i].cacheEvicted / MB << ","
                   << checkpoint.metrics[i].sourceDropped / MB << ","
                   << checkpoint.metrics[i].sent / MB << ","
                   << checkpoint.metrics[i].delivered / MB << ","
                   << (checkpoint.metrics[i].sent - checkpoint.metrics[i].delivered) / MB << ","
                   << checkpoint.pending[i] / MB << "," << checkpoint.peakCacheBytes / MB << "," << seed << "\n";
        }
    }
}

} // namespace

int main(int argc, char* argv[])
{
    std::string linkCsv;
    std::string output;
    std::string stateId = "S1";
    std::string strategyName = "FIFO";
    double startMin = 0.0;
    double endMin = 23.5;
    uint64_t seed = 31;
    double linkUpdateSeconds = DEFAULT_LINK_UPDATE_SECONDS;
    double cacheCapacityMb = DEFAULT_CACHE_CAPACITY_MB;
    std::string recordSizes = "76,43,128,1041,4354778,258715";
    std::string packetSizes = "76,43,128,1041,1472,1472";
    std::string ratesMbps = "0.000050665,0.000028665,0.051200,0.000069400,1.667848,0.413944";

    CommandLine cmd(__FILE__);
    cmd.AddValue("linkCsv", "CSV containing time-varying link samples", linkCsv);
    cmd.AddValue("output", "CSV output path", output);
    cmd.AddValue("stateId", "State label", stateId);
    cmd.AddValue("strategy", "Cache strategy", strategyName);
    cmd.AddValue("startMin", "State start in minutes", startMin);
    cmd.AddValue("endMin", "State end in minutes", endMin);
    cmd.AddValue("seed", "Random seed", seed);
    cmd.AddValue("linkUpdateSeconds", "Link update interval; raw CSV samples are linearly interpolated", linkUpdateSeconds);
    cmd.AddValue("cacheCapacityMb", "Application cache capacity in decimal MB", cacheCapacityMb);
    cmd.AddValue("recordSizes", "Six logical record sizes in bytes: D1,D2,D3,D4,V1,I1", recordSizes);
    cmd.AddValue("packetSizes", "Six transport payload sizes in bytes: D1,D2,D3,D4,V1,I1", packetSizes);
    cmd.AddValue("ratesMbps", "Six generation rates in Mbps: D1,D2,D3,D4,V1,I1", ratesMbps);
    cmd.Parse(argc, argv);

    if (linkCsv.empty() || output.empty())
    {
        NS_FATAL_ERROR("--linkCsv and --output are required");
    }
    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(1);

    auto samples = ReadSamples(linkCsv, startMin, endMin);
    double duration = (endMin - startMin) * 60.0;
    if (linkUpdateSeconds <= 0.0)
    {
        NS_FATAL_ERROR("--linkUpdateSeconds must be positive");
    }
    if (cacheCapacityMb < 0.0)
    {
        NS_FATAL_ERROR("--cacheCapacityMb must be non-negative");
    }
    auto parseUnsignedList = [](const std::string& value) {
        std::vector<uint32_t> result;
        std::stringstream ss(value);
        std::string item;
        while (std::getline(ss, item, ','))
        {
            result.push_back(static_cast<uint32_t>(std::stoul(Trim(item))));
        }
        return result;
    };
    auto parseDoubleList = [](const std::string& value) {
        std::vector<double> result;
        std::stringstream ss(value);
        std::string item;
        while (std::getline(ss, item, ','))
        {
            result.push_back(std::stod(Trim(item)));
        }
        return result;
    };
    auto recordBytes = parseUnsignedList(recordSizes);
    auto packetBytes = parseUnsignedList(packetSizes);
    auto rates = parseDoubleList(ratesMbps);
    if (recordBytes.size() != STREAMS.size() || packetBytes.size() != STREAMS.size() ||
        rates.size() != STREAMS.size())
    {
        NS_FATAL_ERROR("--recordSizes, --packetSizes and --ratesMbps must each contain six comma-separated values");
    }
    for (double rate : rates)
    {
        if (rate <= 0.0)
        {
            NS_FATAL_ERROR("All --ratesMbps values must be positive");
        }
    }
    for (uint32_t bytes : recordBytes)
    {
        if (bytes == 0)
        {
            NS_FATAL_ERROR("All --recordSizes values must be positive");
        }
    }
    for (uint32_t bytes : packetBytes)
    {
        if (bytes == 0)
        {
            NS_FATAL_ERROR("All --packetSizes values must be positive");
        }
    }
    Strategy strategy = ParseStrategy(strategyName);
    bool noCache = strategy == Strategy::NO_CACHE;

    NodeContainer nodes;
    nodes.Create(2);
    InternetStackHelper internet;
    internet.Install(nodes);

    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", DataRateValue(DataRate("2Mbps")));
    p2p.SetChannelAttribute("Delay", TimeValue(MilliSeconds(samples.front().rttMs / 2.0)));
    NetDeviceContainer devices = p2p.Install(nodes);

    Ipv4AddressHelper addresses;
    addresses.SetBase("10.0.0.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = addresses.Assign(devices);

    Ptr<PointToPointNetDevice> senderDevice = DynamicCast<PointToPointNetDevice>(devices.Get(0));
    Ptr<PointToPointNetDevice> receiverDevice = DynamicCast<PointToPointNetDevice>(devices.Get(1));
    Ptr<PointToPointChannel> channel = DynamicCast<PointToPointChannel>(devices.Get(0)->GetChannel());
    Ptr<RateErrorModel> errorModel = CreateObject<RateErrorModel>();
    errorModel->SetUnit(RateErrorModel::ERROR_UNIT_PACKET);
    receiverDevice->SetReceiveErrorModel(errorModel);
    senderDevice->SetDataRate(DataRate(static_cast<uint64_t>(samples.front().capacityMbps * 1000000.0)));

    std::vector<Metrics> metrics(STREAMS.size());
    Ptr<ReceiverApplication> receiver = CreateObject<ReceiverApplication>();
    receiver->SetMetrics(&metrics);
    nodes.Get(1)->AddApplication(receiver);
    receiver->SetStartTime(Seconds(0));
    receiver->SetStopTime(Seconds(duration + 2.0));

    Ptr<Socket> socket = Socket::CreateSocket(nodes.Get(0), UdpSocketFactory::GetTypeId());
    Ptr<CacheApplication> source = CreateObject<CacheApplication>();
    source->Configure(socket,
                      interfaces.GetAddress(1),
                      samples,
                      strategy,
                      &metrics,
                      duration,
                      noCache,
                      startMin,
                      linkUpdateSeconds,
                      recordBytes,
                      packetBytes,
                      rates,
                      cacheCapacityMb);
    nodes.Get(0)->AddApplication(source);
    source->SetStartTime(Seconds(0));
    source->SetStopTime(Seconds(duration + 2.0));

    for (double time = 0.0; time < duration - EPSILON; time += linkUpdateSeconds)
    {
        Simulator::Schedule(Seconds(time), [&, time]() {
            LinkSample sample = InterpolateSample(samples, startMin + time / 60.0);
            senderDevice->SetDataRate(DataRate(static_cast<uint64_t>(sample.capacityMbps * 1000000.0)));
            errorModel->SetRate(sample.lossRate);
            channel->SetAttribute("Delay", TimeValue(MilliSeconds(sample.rttMs / 2.0)));
        });
    }

    Simulator::Stop(Seconds(duration + 2.0));
    Simulator::Run();
    Simulator::Destroy();

    std::vector<double> pending = source->GetPendingSnapshot();
    double peakCache = noCache ? 0.0 : source->GetPeakCacheBytes();
    WriteResults(output, stateId, strategyName, metrics, pending, peakCache, source->GetCheckpoints(), seed);
    return 0;
}
