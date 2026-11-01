// Four-node file-assembly ablation with actual TCP CUBIC/TCP BBR/QUIC BBR.
// Real codec artifacts are prepared externally and verified against N1 input.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/quic-module.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <deque>
#include <fstream>
#include <iomanip>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>
using namespace ns3;
using Bytes=std::vector<uint8_t>;
struct Item {
 uint32_t id,stream,rawSize,encSize,generated=0,arrived=0;
 std::string rawPath,encPath,rawChoices,compChoices,status="assembling";
 double first,deadline,encode,decode,rawDecode,assembled=-1,ready=-1,start=-1,received=-1,done=-1;
 int protocol=-1;
};
struct Link {double time,capacity,rtt,loss;};
std::vector<std::string> Split(const std::string& s,char sep) {std::vector<std::string> o;std::stringstream ss(s);std::string x;while(std::getline(ss,x,sep))o.push_back(x);return o;}
void Put(Bytes& b,uint32_t n) {for(int s=24;s>=0;s-=8)b.push_back((n>>s)&255);}
uint32_t Get(const Bytes& b,size_t p) {return (uint32_t(b[p])<<24)|(uint32_t(b[p+1])<<16)|(uint32_t(b[p+2])<<8)|b[p+3];}
struct Pending {Bytes data;size_t pos=0;};

class Experiment {
public:
 std::vector<Item> items;std::vector<Link> links;
 NodeContainer nodes;NetDeviceContainer bottleneck;Ptr<PointToPointChannel> channel;
 std::array<Ptr<RateErrorModel>,2> errors;
 std::array<Ptr<Socket>,3> clients;std::array<bool,3> connected{false,false,false};
 Ptr<Socket> source;bool sourceConnected=false,pumpingSource=false,pumpingDown=false;
 std::deque<Pending> upstream;std::map<Ptr<Socket>,Bytes> buffers;
 std::vector<Bytes> assembly;std::vector<uint32_t> queue;int active=-1;
 Bytes frame;size_t framePos=0,linkIndex=0;Ipv4Address n1Address,n3Address;
 std::map<std::string,std::shared_ptr<Bytes>> assets;
 std::array<double,6> rates{};
 bool compression=true,adaptive=true,cache=true;
 double capacityBytes=50000000,queueBytes=0,peakQueue=0,assemblyBytes=0,peakAssembly=0;
 uint64_t linkDrops=0,wirePackets=0;std::ofstream decisions;

 const Bytes& Asset(const std::string& path) {
  auto it=assets.find(path);if(it!=assets.end())return *it->second;
  std::ifstream f(path,std::ios::binary);NS_ABORT_MSG_IF(!f,"Cannot open "<<path);
  auto b=std::make_shared<Bytes>(std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>());
  assets[path]=b;return *b;
 }
 uint32_t Size(uint32_t id) const{return compression?items[id].encSize:items[id].rawSize;}
 double Score(uint32_t id) const {auto &i=items[id];double offered=rates[i.stream]*double(Size(id))/i.rawSize;return std::pow(i.stream+1.,-1.5)/(1+offered/links[linkIndex].capacity);}
 void Load(std::string input,double duration) {
  std::ifstream f(input+"/files.tsv");std::string line;std::getline(f,line);
  while(std::getline(f,line)){auto v=Split(line,'\t');if(v.size()!=13)continue;Item i;
   i.id=std::stoul(v[0]);i.stream=std::stoul(v[1]);i.rawPath=v[2];i.encPath=v[3];i.rawSize=std::stoul(v[4]);i.encSize=std::stoul(v[5]);
   i.first=std::stod(v[6]);i.deadline=std::stod(v[7]);i.encode=std::stod(v[8]);i.decode=std::stod(v[9]);i.rawDecode=std::stod(v[10]);i.rawChoices=v[11];i.compChoices=v[12];items.push_back(i);
  }
  assembly.resize(items.size());std::ifstream l(input+"/link.csv");std::getline(l,line);
  while(std::getline(l,line)){auto v=Split(line,',');links.push_back({std::stod(v[0])*60,std::stod(v[2]),std::stod(v[3]),std::stod(v[4])});}
  std::ifstream e(input+"/events.tsv");std::getline(e,line);
  while(std::getline(e,line)){auto v=Split(line,'\t');double t=std::stod(v[0]);uint32_t id=std::stoul(v[1]),offset=std::stoul(v[2]),len=std::stoul(v[3]);
   if(t<duration){items[id].generated+=len;rates[items[id].stream]+=len*8./duration/1e6;Simulator::Schedule(Seconds(t),&Experiment::Generate,this,id,offset,len);}
  }
  NS_ABORT_MSG_IF(items.empty()||links.empty(),"No experiment inputs");
 }
 bool Accept(Ptr<Socket>,const Address&){return true;}
 void SourceAccepted(Ptr<Socket> s,const Address&){s->SetRecvCallback(MakeCallback(&Experiment::N1Receive,this));}
 void SinkAccepted(Ptr<Socket> s,const Address&){s->SetRecvCallback(MakeCallback(&Experiment::N3Receive,this));}
 void Failed(Ptr<Socket>){NS_FATAL_ERROR("Transport connection failed");}
 void SourceConnected(Ptr<Socket>){sourceConnected=true;PumpSource();}
 void ConnectSource(){source->Connect(InetSocketAddress(n1Address,10000));}
 void SourceWritable(Ptr<Socket>,uint32_t){PumpSource();}
 void DownConnected(Ptr<Socket> s){for(int k=0;k<3;k++)if(clients[k]==s)connected[k]=true;PumpDown();}
 void DownWritable(Ptr<Socket>,uint32_t){PumpDown();}
 void Generate(uint32_t id,uint32_t offset,uint32_t length){
  const auto& raw=Asset(items[id].rawPath);NS_ABORT_MSG_IF(offset+length>raw.size(),"Input bounds");
  Pending p;Put(p.data,id);Put(p.data,offset);Put(p.data,length);p.data.insert(p.data.end(),raw.begin()+offset,raw.begin()+offset+length);upstream.push_back(std::move(p));PumpSource();
 }
 void PumpSource(){
  if(!sourceConnected||pumpingSource)return;pumpingSource=true;
  while(!upstream.empty()) {auto&p=upstream.front();auto n=std::min<size_t>({p.data.size()-p.pos,1448,source->GetTxAvailable()});if(!n)break;
   int sent=source->Send(Create<Packet>(p.data.data()+p.pos,n));if(sent<=0)break;p.pos+=sent;if(p.pos==p.data.size())upstream.pop_front();}
  pumpingSource=false;
 }
 void ReadSocket(Ptr<Socket> s){Ptr<Packet> p;auto&b=buffers[s];while((p=s->Recv())){if(!p->GetSize())break;size_t old=b.size();b.resize(old+p->GetSize());p->CopyData(b.data()+old,p->GetSize());}}
 void N1Receive(Ptr<Socket> s){
  ReadSocket(s);auto&b=buffers[s];size_t cursor=0;
  while(b.size()-cursor>=12){uint32_t id=Get(b,cursor),off=Get(b,cursor+4),len=Get(b,cursor+8);if(b.size()-cursor<12+len)break;
   NS_ABORT_MSG_IF(id>=items.size(),"Bad source item id");auto&i=items[id];auto&a=assembly[id];
   NS_ABORT_MSG_IF(off!=a.size(),"Source stream reconstruction gap");a.insert(a.end(),b.begin()+cursor+12,b.begin()+cursor+12+len);i.arrived+=len;assemblyBytes+=len;peakAssembly=std::max(peakAssembly,assemblyBytes);
   if(i.arrived==i.rawSize){NS_ABORT_MSG_IF(a!=Asset(i.rawPath),"N1 assembled bytes mismatch");i.assembled=Simulator::Now().GetSeconds();
    double when=std::max(i.assembled,i.deadline);Simulator::Schedule(Seconds(when-i.assembled),&Experiment::BeginEncoding,this,id);}
   cursor+=12+len;
  }
  if(cursor)b.erase(b.begin(),b.begin()+cursor);
 }
 void BeginEncoding(uint32_t id){items[id].status="encoding";Simulator::Schedule(Seconds(compression?items[id].encode:0),&Experiment::Ready,this,id);}
 void Ready(uint32_t id){
  auto&i=items[id];i.ready=Simulator::Now().GetSeconds();assemblyBytes-=assembly[id].size();Bytes().swap(assembly[id]);
  if(!cache&&active>=0){i.status="source_dropped";return;}
  i.status="queued";queue.push_back(id);queueBytes+=Size(id);
  // An idle server can admit an item directly, including a file larger than
  // the waiting-queue capacity. The active service item is not a waiting item.
  if(active<0){Dispatch();return;}
  if(cache){while(queueBytes>capacityBytes&&!queue.empty()){
   auto worst=std::min_element(queue.begin(),queue.end(),[this](auto a,auto b){double sa=Score(a),sb=Score(b);return sa==sb?a>b:sa<sb;});
   uint32_t victim=*worst;items[victim].status="cache_evicted";queueBytes-=Size(victim);queue.erase(worst);}}
  Dispatch();peakQueue=std::max(peakQueue,queueBytes);
 }
 void Dispatch(){
  if(active>=0||queue.empty())return;
  auto best=std::max_element(queue.begin(),queue.end(),[this](auto a,auto b){double sa=Score(a),sb=Score(b);return sa==sb?a>b:sa<sb;});
  uint32_t id=*best;queue.erase(best);queueBytes-=Size(id);active=id;auto&i=items[id];
  i.start=Simulator::Now().GetSeconds();i.status="in_service";
  auto&choices=compression?i.compChoices:i.rawChoices;i.protocol=adaptive?choices.at(std::min(linkIndex,choices.size()-1))-'0':2;
  decisions<<std::setprecision(12)<<i.start<<','<<id<<','<<i.stream<<','<<i.protocol<<','<<linkIndex<<','<<links[linkIndex].capacity<<','<<links[linkIndex].rtt<<','<<links[linkIndex].loss<<'\n';
  const auto&payload=Asset(compression?i.encPath:i.rawPath);NS_ABORT_MSG_IF(payload.size()!=Size(id),"Artifact size changed");
  frame.clear();Put(frame,id);Put(frame,payload.size());frame.insert(frame.end(),payload.begin(),payload.end());framePos=0;
  int k=i.protocol;
  if(!clients[k]){
   clients[k]=Socket::CreateSocket(nodes.Get(1),TypeId::LookupByName(k==0?"ns3::QuicSocketFactory":"ns3::TcpSocketFactory"));
   if(k){auto tcp=DynamicCast<TcpSocketBase>(clients[k]);if(k==1)tcp->SetCongestionControlAlgorithm(CreateObject<TcpBbr>());else tcp->SetCongestionControlAlgorithm(CreateObject<TcpCubic>());}
   clients[k]->SetConnectCallback(MakeCallback(&Experiment::DownConnected,this),MakeCallback(&Experiment::Failed,this));
   clients[k]->SetSendCallback(MakeCallback(&Experiment::DownWritable,this));clients[k]->SetRecvCallback(MakeCallback(&Experiment::AckReceive,this));
   clients[k]->Bind();clients[k]->Connect(InetSocketAddress(n3Address,11000+k));
  }
  PumpDown();
 }
 void PumpDown(){
  if(active<0||pumpingDown)return;int k=items[active].protocol;if(!connected[k])return;pumpingDown=true;
  auto s=clients[k];while(framePos<frame.size()){
   auto n=std::min<size_t>({frame.size()-framePos,1448,s->GetTxAvailable()});if(!n)break;
   // The QUIC module's default Send stripes data over streams. A file frame
   // requires ordered bytes, so use one explicit bidirectional stream.
   int sent=s->Send(Create<Packet>(frame.data()+framePos,n),k==0?1:0);if(sent<=0)break;framePos+=sent;}
  pumpingDown=false;
  if(framePos==frame.size()){
   // The finite transport buffer owns these bytes and performs its own ACKs
   // and retransmissions. Do not gate application scheduling on a second ACK.
   if(items[active].status=="in_service")items[active].status="in_transport";
   active=-1;frame.clear();Simulator::ScheduleNow(&Experiment::Dispatch,this);
  }
 }
 void N3Receive(Ptr<Socket> s){
  ReadSocket(s);auto&b=buffers[s];
  while(b.size()>=8){uint32_t id=Get(b,0),len=Get(b,4);NS_ABORT_MSG_IF(id>=items.size(),"Bad downstream id");if(b.size()<8+len)return;
   auto&i=items[id];const auto&expected=Asset(compression?i.encPath:i.rawPath);
   if (len!=expected.size()||!std::equal(expected.begin(),expected.end(),b.begin()+8)){
    auto same=std::mismatch(expected.begin(),expected.begin()+std::min<size_t>(len,expected.size()),b.begin()+8);
    size_t first=std::distance(expected.begin(),same.first);
    std::cerr<<"PAYLOAD_MISMATCH t="<<Simulator::Now().GetSeconds()<<" id="<<id<<" stream="<<i.stream<<" len="<<len<<" expected="<<expected.size()<<" first="<<first<<" received-byte="<<(first<len?int(b[8+first]):-1)<<" expected-byte="<<(first<expected.size()?int(expected[first]):-1)<<std::endl;
    NS_ABORT_MSG("N3 payload mismatch");
   }
   i.received=Simulator::Now().GetSeconds();i.status="decoding";
   Simulator::Schedule(Seconds(compression?i.decode:i.rawDecode),&Experiment::Decoded,this,id);
   b.erase(b.begin(),b.begin()+8+len);
  }
 }
 void Decoded(uint32_t id){items[id].done=Simulator::Now().GetSeconds();items[id].status="delivered";}
 void AckReceive(Ptr<Socket> s){
  ReadSocket(s);auto&b=buffers[s];while(b.size()>=4){uint32_t id=Get(b,0);NS_ABORT_MSG_IF(active!=int(id),"Unexpected application acknowledgement");b.erase(b.begin(),b.begin()+4);active=-1;frame.clear();Simulator::ScheduleNow(&Experiment::Dispatch,this);}
 }
 void Update(size_t index){linkIndex=index;auto&l=links[index];channel->SetAttribute("Delay",TimeValue(Seconds(l.rtt/2000.0)));
  for(int k=0;k<2;k++){DynamicCast<PointToPointNetDevice>(bottleneck.Get(k))->SetDataRate(DataRate(uint64_t(l.capacity*1e6)));errors[k]->SetRate(l.loss);}}
 void Drop(Ptr<const Packet>){linkDrops++;}
 void Tx(Ptr<const Packet>){wirePackets++;}
 void Setup(){
  Config::SetDefault("ns3::TcpSocket::SegmentSize",UintegerValue(1448));
  Config::SetDefault("ns3::TcpSocket::SndBufSize",UintegerValue(131072));Config::SetDefault("ns3::TcpSocket::RcvBufSize",UintegerValue(131072));
  Config::SetDefault("ns3::QuicL4Protocol::SocketType",TypeIdValue(QuicBbr::GetTypeId()));
  Config::SetDefault("ns3::QuicSocketBase::MaxStreamData",UintegerValue(131072));
  Config::SetDefault("ns3::QuicSocketBase::IdleTimeout",TimeValue(Seconds(7200)));
  nodes.Create(4);QuicHelper stack;stack.InstallQuic(nodes);
  PointToPointHelper p;p.SetDeviceAttribute("DataRate",StringValue("100Mbps"));p.SetChannelAttribute("Delay",TimeValue(Seconds(0)));
  auto access=p.Install(NodeContainer(nodes.Get(0),nodes.Get(1)));auto exit=p.Install(NodeContainer(nodes.Get(2),nodes.Get(3)));
  p.SetDeviceAttribute("DataRate",StringValue("2Mbps"));p.SetChannelAttribute("Delay",TimeValue(MilliSeconds(40)));
  bottleneck=p.Install(NodeContainer(nodes.Get(1),nodes.Get(2)));channel=DynamicCast<PointToPointChannel>(bottleneck.Get(0)->GetChannel());
  for(int k=0;k<2;k++){
   errors[k]=CreateObject<RateErrorModel>();errors[k]->SetUnit(RateErrorModel::ERROR_UNIT_PACKET);
   auto rng=CreateObject<UniformRandomVariable>();rng->SetStream(100+k);errors[k]->SetRandomVariable(rng);
   bottleneck.Get(k)->SetAttribute("ReceiveErrorModel",PointerValue(errors[k]));
   bottleneck.Get(k)->TraceConnectWithoutContext("PhyRxDrop",MakeCallback(&Experiment::Drop,this));
   bottleneck.Get(k)->TraceConnectWithoutContext("PhyTxBegin",MakeCallback(&Experiment::Tx,this));
  }
  Ipv4AddressHelper a;a.SetBase("10.1.1.0","255.255.255.0");auto ai=a.Assign(access);n1Address=ai.GetAddress(1);
  a.SetBase("10.1.2.0","255.255.255.0");a.Assign(bottleneck);a.SetBase("10.1.3.0","255.255.255.0");auto ei=a.Assign(exit);n3Address=ei.GetAddress(1);
  Ipv4GlobalRoutingHelper::PopulateRoutingTables();Update(0);
  for(size_t i=1;i<links.size();i++)Simulator::Schedule(Seconds(links[i].time),&Experiment::Update,this,i);
  auto n1=Socket::CreateSocket(nodes.Get(1),TcpSocketFactory::GetTypeId());n1->Bind(InetSocketAddress(Ipv4Address::GetAny(),10000));n1->Listen();n1->SetAcceptCallback(MakeCallback(&Experiment::Accept,this),MakeCallback(&Experiment::SourceAccepted,this));n1->SetRecvCallback(MakeCallback(&Experiment::N1Receive,this));
  for(int k=0;k<3;k++){
   auto sink=Socket::CreateSocket(nodes.Get(3),TypeId::LookupByName(k==0?"ns3::QuicSocketFactory":"ns3::TcpSocketFactory"));
   sink->Bind(InetSocketAddress(Ipv4Address::GetAny(),11000+k));sink->Listen();sink->SetAcceptCallback(MakeCallback(&Experiment::Accept,this),MakeCallback(&Experiment::SinkAccepted,this));sink->SetRecvCallback(MakeCallback(&Experiment::N3Receive,this));
  }
  source=Socket::CreateSocket(nodes.Get(0),TcpSocketFactory::GetTypeId());DynamicCast<TcpSocketBase>(source)->SetCongestionControlAlgorithm(CreateObject<TcpCubic>());
  source->SetConnectCallback(MakeCallback(&Experiment::SourceConnected,this),MakeCallback(&Experiment::Failed,this));source->SetSendCallback(MakeCallback(&Experiment::SourceWritable,this));source->Bind();Simulator::ScheduleNow(&Experiment::ConnectSource,this);
 }
 void Save(std::string path){
  std::ofstream f(path);f<<"id,stream,status,generated_raw_bytes,arrived_raw_bytes,raw_file_bytes,wire_file_bytes,first_s,assembled_s,ready_s,tx_start_s,received_s,decoded_s,protocol\n"<<std::setprecision(12);
  for(auto&i:items)f<<i.id<<','<<i.stream<<','<<i.status<<','<<i.generated<<','<<i.arrived<<','<<i.rawSize<<','<<Size(i.id)<<','<<i.first<<','<<i.assembled<<','<<i.ready<<','<<i.start<<','<<i.received<<','<<i.done<<','<<i.protocol<<'\n';
  std::ofstream metrics(path+".metrics.json");metrics<<"{\"peak_queue_bytes\":"<<peakQueue<<",\"peak_assembly_bytes\":"<<peakAssembly<<",\"link_dropped_packets\":"<<linkDrops<<",\"wire_packets_both_directions\":"<<wirePackets<<",\"remaining_queue_bytes\":"<<queueBytes<<"}\n";
 }
};
int main(int argc,char**argv){
 std::string input,output,variant="FULL";double duration=3600,drain=0;uint32_t seed=31;double cacheBytes=50000000;
 CommandLine cmd;cmd.AddValue("input","Prepared artifact directory",input);cmd.AddValue("output","Per-file results CSV",output);cmd.AddValue("variant","Ablation variant",variant);cmd.AddValue("duration","Source duration seconds",duration);cmd.AddValue("drain","Drain seconds",drain);cmd.AddValue("seed","RNG seed",seed);cmd.AddValue("cacheBytes","Waiting file cache",cacheBytes);cmd.Parse(argc,argv);
 NS_ABORT_MSG_IF(input.empty()||output.empty(),"input and output required");RngSeedManager::SetSeed(seed);RngSeedManager::SetRun(1);
 const std::vector<std::string> validVariants={"FULL","WO_PROTOCOL","WO_COMPRESSION","WO_CACHE","BASELINE","ADD_PROTOCOL","ADD_COMPRESSION","ADD_CACHE"};
 NS_ABORT_MSG_IF(std::find(validVariants.begin(),validVariants.end(),variant)==validVariants.end(),"Unknown ablation variant: "<<variant);
 Experiment e;e.capacityBytes=cacheBytes;
 e.adaptive=variant!="WO_PROTOCOL"&&variant!="BASELINE"&&variant!="ADD_COMPRESSION"&&variant!="ADD_CACHE";
 e.compression=variant!="WO_COMPRESSION"&&variant!="BASELINE"&&variant!="ADD_PROTOCOL"&&variant!="ADD_CACHE";
 e.cache=variant!="WO_CACHE"&&variant!="BASELINE"&&variant!="ADD_PROTOCOL"&&variant!="ADD_COMPRESSION";
 e.decisions.open(output+".decisions.csv");e.decisions<<"time_s,id,stream,protocol,state_index,capacity_mbps,rtt_ms,packet_loss_rate\n";
 e.Load(input,duration);e.Setup();Simulator::Stop(Seconds(duration+drain));Simulator::Run();e.Save(output);Simulator::Destroy();std::cout<<"Completed "<<variant<<" files="<<e.items.size()<<std::endl;
}
