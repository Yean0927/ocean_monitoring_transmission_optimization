/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * QUIC random-interval throughput experiment for the external ns-3.32 QUIC
 * module. This file mirrors the TCP random-interval traffic model used by
 * scratch/tcp-exp.cc: every application packet samples its own size and next
 * send interval from configured ranges.
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/error-model.h"
#include "ns3/flow-monitor-helper.h"
#include "ns3/internet-module.h"
#include "ns3/ipv4-global-routing-helper.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/quic-module.h"
#include "ns3/traffic-control-module.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("QuicVariantsComparisonRandomInterval");

namespace
{

class RandomIntervalQuicApplication : public Application
{
public:
  RandomIntervalQuicApplication ();
  ~RandomIntervalQuicApplication () override;

  void Setup (Address peer,
              uint32_t minPacketSize,
              uint32_t maxPacketSize,
              uint64_t maxBytes,
              Time minInterval,
              Time maxInterval,
              uint32_t numStreams);

private:
  void StartApplication () override;
  void StopApplication () override;
  void SendPacket ();
  void ScheduleNextTx ();

  Ptr<Socket> m_socket;
  Address m_peer;
  EventId m_sendEvent;
  Ptr<UniformRandomVariable> m_intervalRng;
  Ptr<UniformRandomVariable> m_packetSizeRng;
  uint32_t m_minPacketSize;
  uint32_t m_maxPacketSize;
  uint64_t m_maxBytes;
  uint64_t m_totalTx;
  Time m_minInterval;
  Time m_maxInterval;
  uint32_t m_numStreams;
  uint32_t m_lastUsedStream;
  bool m_running;
};

RandomIntervalQuicApplication::RandomIntervalQuicApplication ()
  : m_socket (0),
    m_intervalRng (CreateObject<UniformRandomVariable> ()),
    m_packetSizeRng (CreateObject<UniformRandomVariable> ()),
    m_minPacketSize (1024),
    m_maxPacketSize (1024),
    m_maxBytes (0),
    m_totalTx (0),
    m_minInterval (MilliSeconds (1)),
    m_maxInterval (MilliSeconds (10)),
    m_numStreams (1),
    m_lastUsedStream (1),
    m_running (false)
{
}

RandomIntervalQuicApplication::~RandomIntervalQuicApplication ()
{
  m_socket = 0;
}

void
RandomIntervalQuicApplication::Setup (Address peer,
                                      uint32_t minPacketSize,
                                      uint32_t maxPacketSize,
                                      uint64_t maxBytes,
                                      Time minInterval,
                                      Time maxInterval,
                                      uint32_t numStreams)
{
  m_peer = peer;
  m_minPacketSize = minPacketSize;
  m_maxPacketSize = maxPacketSize;
  m_maxBytes = maxBytes;
  m_minInterval = minInterval;
  m_maxInterval = maxInterval;
  m_numStreams = std::max<uint32_t> (1, numStreams);
  m_intervalRng->SetAttribute ("Min", DoubleValue (m_minInterval.GetSeconds ()));
  m_intervalRng->SetAttribute ("Max", DoubleValue (m_maxInterval.GetSeconds ()));
  m_packetSizeRng->SetAttribute ("Min", DoubleValue (m_minPacketSize));
  m_packetSizeRng->SetAttribute ("Max", DoubleValue (m_maxPacketSize));
}

void
RandomIntervalQuicApplication::StartApplication ()
{
  m_running = true;
  m_totalTx = 0;
  m_lastUsedStream = 1;
  m_socket = Socket::CreateSocket (GetNode (), QuicSocketFactory::GetTypeId ());
  if (m_socket->Bind () == -1)
    {
      NS_FATAL_ERROR ("Failed to bind QUIC socket");
    }
  m_socket->Connect (m_peer);
  m_socket->SetAllowBroadcast (true);
  SendPacket ();
}

void
RandomIntervalQuicApplication::StopApplication ()
{
  m_running = false;
  Simulator::Cancel (m_sendEvent);
  if (m_socket)
    {
      m_socket->Close ();
      m_socket = 0;
    }
}

void
RandomIntervalQuicApplication::SendPacket ()
{
  if (!m_running)
    {
      return;
    }

  uint32_t bytesToSend = static_cast<uint32_t> (std::round (m_packetSizeRng->GetValue ()));
  bytesToSend = std::max (m_minPacketSize, std::min (m_maxPacketSize, bytesToSend));
  if (m_maxBytes > 0)
    {
      if (m_totalTx >= m_maxBytes)
        {
          return;
        }
      bytesToSend = std::min<uint64_t> (bytesToSend, m_maxBytes - m_totalTx);
    }

  Ptr<Packet> packet = Create<Packet> (bytesToSend);
  int actual = m_socket->Send (packet, m_lastUsedStream);
  if (actual > 0)
    {
      m_totalTx += static_cast<uint64_t> (actual);
    }

  m_lastUsedStream++;
  if (m_lastUsedStream > m_numStreams)
    {
      m_lastUsedStream = 1;
    }

  ScheduleNextTx ();
}

void
RandomIntervalQuicApplication::ScheduleNextTx ()
{
  if (!m_running)
    {
      return;
    }
  if (m_maxBytes > 0 && m_totalTx >= m_maxBytes)
    {
      return;
    }

  m_sendEvent = Simulator::Schedule (Seconds (m_intervalRng->GetValue ()),
                                     &RandomIntervalQuicApplication::SendPacket,
                                     this);
}

} // namespace

int
main (int argc, char *argv[])
{
  std::string transportProt = "QuicBbr";
  double errorP = 0.0;
  std::string bandwidth = "2Mbps";
  std::string delay = "0.01ms";
  std::string accessBandwidth = "100Mbps";
  std::string accessDelay = "0ms";
  double dataMbytes = 0.0;
  uint32_t mtuBytes = 1400;
  uint32_t minPacketSize = 1448;
  uint32_t maxPacketSize = 1448;
  double minSendIntervalMs = 1.0;
  double maxSendIntervalMs = 10.0;
  uint32_t numStreams = 1;
  float duration = 5.0;
  uint32_t run = 0;
  bool flowMonitor = false;
  std::string queueDiscType = "ns3::PfifoFastQueueDisc";

  CommandLine cmd;
  cmd.AddValue ("transport_prot", "QUIC congestion control, for example QuicBbr", transportProt);
  cmd.AddValue ("error_p", "Packet error rate on the bottleneck link", errorP);
  cmd.AddValue ("bandwidth", "Bottleneck bandwidth", bandwidth);
  cmd.AddValue ("delay", "Bottleneck one-way delay", delay);
  cmd.AddValue ("access_bandwidth", "Access link bandwidth", accessBandwidth);
  cmd.AddValue ("access_delay", "Access link delay", accessDelay);
  cmd.AddValue ("data", "Number of MBytes to transmit, 0 means unlimited", dataMbytes);
  cmd.AddValue ("mtu", "Queue sizing MTU in bytes", mtuBytes);
  cmd.AddValue ("minPacketSize", "Minimum application packet size in bytes", minPacketSize);
  cmd.AddValue ("maxPacketSize", "Maximum application packet size in bytes", maxPacketSize);
  cmd.AddValue ("minSendIntervalMs", "Minimum random send interval in ms", minSendIntervalMs);
  cmd.AddValue ("maxSendIntervalMs", "Maximum random send interval in ms", maxSendIntervalMs);
  cmd.AddValue ("numStreams", "Number of QUIC streams used round-robin", numStreams);
  cmd.AddValue ("duration", "Time to allow the flow to run in seconds", duration);
  cmd.AddValue ("run", "Run index for repeatable random streams", run);
  cmd.AddValue ("flow_monitor", "Enable flow monitor", flowMonitor);
  cmd.AddValue ("queue_disc_type", "Queue disc type for gateway", queueDiscType);
  cmd.Parse (argc, argv);

  if (minPacketSize == 0 || maxPacketSize == 0 || maxPacketSize < minPacketSize)
    {
      NS_FATAL_ERROR ("Packet size bounds must be positive and max >= min");
    }
  if (minSendIntervalMs <= 0 || maxSendIntervalMs <= 0 || maxSendIntervalMs < minSendIntervalMs)
    {
      NS_FATAL_ERROR ("Send interval bounds must be positive and max >= min");
    }

  std::string transportTypeId = std::string ("ns3::") + transportProt;
  SeedManager::SetSeed (1);
  SeedManager::SetRun (run);
  Time::SetResolution (Time::NS);

  Config::SetDefault ("ns3::QuicSocketBase::SocketRcvBufSize", UintegerValue (1 << 21));
  Config::SetDefault ("ns3::QuicSocketBase::SocketSndBufSize", UintegerValue (1 << 21));
  Config::SetDefault ("ns3::QuicStreamBase::StreamSndBufSize", UintegerValue (1 << 21));
  Config::SetDefault ("ns3::QuicStreamBase::StreamRcvBufSize", UintegerValue (1 << 21));

  TypeId tcpTid;
  NS_ABORT_MSG_UNLESS (TypeId::LookupByNameFailSafe (transportTypeId, &tcpTid),
                       "TypeId " << transportTypeId << " not found");
  Config::SetDefault ("ns3::QuicL4Protocol::SocketType", TypeIdValue (tcpTid));

  double serverStartTime = 0.99;
  double clientStartTime = 2.0;
  double stopTime = clientStartTime + duration;

  NodeContainer gateways;
  gateways.Create (2);
  NodeContainer sources;
  sources.Create (1);
  NodeContainer sinks;
  sinks.Create (1);

  Ptr<UniformRandomVariable> uv = CreateObject<UniformRandomVariable> ();
  uv->SetStream (50);
  RateErrorModel errorModel;
  errorModel.SetRandomVariable (uv);
  errorModel.SetUnit (RateErrorModel::ERROR_UNIT_PACKET);
  errorModel.SetRate (errorP);

  PointToPointHelper bottleneckLink;
  bottleneckLink.SetDeviceAttribute ("DataRate", StringValue (bandwidth));
  bottleneckLink.SetChannelAttribute ("Delay", StringValue (delay));
  bottleneckLink.SetDeviceAttribute ("ReceiveErrorModel", PointerValue (&errorModel));

  PointToPointHelper accessLink;
  accessLink.SetDeviceAttribute ("DataRate", StringValue (accessBandwidth));
  accessLink.SetChannelAttribute ("Delay", StringValue (accessDelay));

  PointToPointHelper localLink;
  localLink.SetDeviceAttribute ("DataRate", StringValue (accessBandwidth));
  localLink.SetChannelAttribute ("Delay", StringValue (accessDelay));

  QuicHelper stack;
  stack.InstallQuic (sources);
  stack.InstallQuic (sinks);
  stack.InstallQuic (gateways);

  TrafficControlHelper tchPfifo;
  tchPfifo.SetRootQueueDisc ("ns3::PfifoFastQueueDisc");
  TrafficControlHelper tchCoDel;
  tchCoDel.SetRootQueueDisc ("ns3::CoDelQueueDisc");

  DataRate accessB (accessBandwidth);
  DataRate bottleB (bandwidth);
  Time accessD (accessDelay);
  Time bottleD (delay);
  uint32_t queueBytes = (std::min (accessB, bottleB).GetBitRate () / 8) *
                        ((accessD + bottleD) * 2).GetSeconds ();
  Config::SetDefault ("ns3::PfifoFastQueueDisc::MaxSize",
                      QueueSizeValue (QueueSize (QueueSizeUnit::PACKETS,
                                                 std::max<uint32_t> (1, queueBytes / mtuBytes))));
  Config::SetDefault ("ns3::CoDelQueueDisc::MaxSize",
                      QueueSizeValue (QueueSize (QueueSizeUnit::BYTES,
                                                 std::max<uint32_t> (1, queueBytes))));

  Ipv4AddressHelper address;
  address.SetBase ("10.0.0.0", "255.255.255.0");

  NetDeviceContainer devices = accessLink.Install (sources.Get (0), gateways.Get (0));
  tchPfifo.Install (devices);
  address.NewNetwork ();
  address.Assign (devices);

  devices = localLink.Install (gateways.Get (1), sinks.Get (0));
  if (queueDiscType.compare ("ns3::CoDelQueueDisc") == 0)
    {
      tchCoDel.Install (devices);
    }
  else
    {
      tchPfifo.Install (devices);
    }
  address.NewNetwork ();
  Ipv4InterfaceContainer sinkInterfaces = address.Assign (devices);

  devices = bottleneckLink.Install (gateways.Get (0), gateways.Get (1));
  if (queueDiscType.compare ("ns3::CoDelQueueDisc") == 0)
    {
      tchCoDel.Install (devices);
    }
  else
    {
      tchPfifo.Install (devices);
    }
  address.NewNetwork ();
  address.Assign (devices);

  Ipv4GlobalRoutingHelper::PopulateRoutingTables ();

  uint16_t port = 50000;
  Address sinkLocalAddress (InetSocketAddress (Ipv4Address::GetAny (), port));
  AddressValue remoteAddress (InetSocketAddress (sinkInterfaces.GetAddress (1), port));

  PacketSinkHelper sinkHelper ("ns3::QuicSocketFactory", sinkLocalAddress);
  sinkHelper.SetAttribute ("Protocol", TypeIdValue (QuicSocketFactory::GetTypeId ()));
  ApplicationContainer serverApps = sinkHelper.Install (sinks.Get (0));

  Ptr<RandomIntervalQuicApplication> randomSender = CreateObject<RandomIntervalQuicApplication> ();
  uint64_t maxBytes = dataMbytes > 0 ? static_cast<uint64_t> (dataMbytes * 1000000.0) : 0;
  randomSender->Setup (remoteAddress.Get (),
                       minPacketSize,
                       maxPacketSize,
                       maxBytes,
                       MilliSeconds (minSendIntervalMs),
                       MilliSeconds (maxSendIntervalMs),
                       numStreams);
  sources.Get (0)->AddApplication (randomSender);
  ApplicationContainer clientApps;
  clientApps.Add (randomSender);

  serverApps.Start (Seconds (serverStartTime));
  clientApps.Start (Seconds (clientStartTime));
  clientApps.Stop (Seconds (stopTime));
  serverApps.Stop (Seconds (stopTime + 0.1));

  FlowMonitorHelper flowHelper;
  if (flowMonitor)
    {
      flowHelper.InstallAll ();
    }

  Simulator::Stop (Seconds (stopTime + 0.1));
  Simulator::Run ();

  uint64_t totalRxBytes = 0;
  Ptr<PacketSink> sink = DynamicCast<PacketSink> (serverApps.Get (0));
  if (sink)
    {
      totalRxBytes = sink->GetTotalRx ();
    }

  double averageThroughput = totalRxBytes * 8.0 / duration / 1000000.0;
  std::cout << std::fixed << std::setprecision (6);
  std::cout << "protocol=" << transportTypeId
            << " trafficMode=random-interval"
            << " capacity=" << bandwidth
            << " oneWayDelay=" << delay
            << " packetLossRate=" << errorP
            << " minPacketSize=" << minPacketSize
            << " maxPacketSize=" << maxPacketSize
            << " minSendIntervalMs=" << minSendIntervalMs
            << " maxSendIntervalMs=" << maxSendIntervalMs
            << " duration=" << duration
            << " totalRxBytes=" << totalRxBytes
            << " averageThroughput=" << averageThroughput << " Mbit/s"
            << std::endl;

  Simulator::Destroy ();
  return 0;
}
