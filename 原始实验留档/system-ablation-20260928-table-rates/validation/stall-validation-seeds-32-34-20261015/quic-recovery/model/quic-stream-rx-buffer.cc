/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2019 SIGNET Lab, Department of Information Engineering, University of Padova
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Authors: Alvise De Biasio <alvise.debiasio@gmail.com>
 *          Federico Chiariotti <chiariotti.federico@gmail.com>
 *          Michele Polese <michele.polese@gmail.com>
 *          Davide Marcato <davidemarcato@outlook.com>
 *
 */

#include "ns3/packet.h"
#include "ns3/fatal-error.h"
#include "ns3/log.h"
// #include "ns3/ipv4-end-point-demux.h"
// #include "ns3/ipv6-end-point-demux.h"
// #include "ns3/ipv4-end-point.h"
// #include "ns3/ipv6-end-point.h"
// #include "ns3/ipv4-l3-protocol.h"
// #include "ns3/ipv6-l3-protocol.h"
// #include "ns3/ipv6-routing-protocol.h"
#include <algorithm>
#include "quic-stream-rx-buffer.h"
#include "quic-subheader.h"

namespace ns3 {

NS_LOG_COMPONENT_DEFINE ("QuicStreamRxBuffer");

QuicStreamRxItem::QuicStreamRxItem ()
  : m_packet (0),
  m_offset (0),
  m_fin (false)
{
}

QuicStreamRxItem::QuicStreamRxItem (const QuicStreamRxItem &other)
  : m_packet (other.m_packet),
  m_offset (other.m_offset),
  m_fin (other.m_fin)
{
}

void
QuicStreamRxItem::Print (std::ostream &os) const
{
  os << "[OFF " << m_offset << "]";

  if (m_fin)
    {
      os << "|fin|";
    }

}

NS_OBJECT_ENSURE_REGISTERED (QuicStreamRxBuffer);

TypeId
QuicStreamRxBuffer::GetTypeId (void)
{
  static TypeId tid = TypeId ("ns3::QuicStreamRxBuffer")
    .SetParent<Object> ()
    .SetGroupName ("Internet")
    .AddConstructor<QuicStreamRxBuffer> ()
  ;
  return tid;
}

QuicStreamRxBuffer::QuicStreamRxBuffer ()
  : m_numBytesInBuffer (0),
  m_finalSize (0),
  m_maxBuffer (131072),
  m_recvFin (
    false)
{
  m_streamRecvList = QuicStreamRxPacketList ();
}

QuicStreamRxBuffer::~QuicStreamRxBuffer ()
{
}

bool
QuicStreamRxBuffer::Add (Ptr<Packet> p, const QuicSubheader& sub)
{
  // Store only uncovered byte intervals; overlapping retransmissions consume
  // no receive credit twice. Each list entry is disjoint and ordered.
  uint64_t cursor = sub.GetOffset ();
  const uint64_t end = cursor + p->GetSize ();
  std::vector<std::pair<uint64_t, uint32_t>> ranges;
  for (auto existing : m_streamRecvList)
    {
      uint64_t a = existing->m_offset;
      uint64_t b = a + existing->m_packet->GetSize ();
      if (b <= cursor) continue;
      if (a >= end) break;
      if (a > cursor) ranges.emplace_back (cursor, a - cursor);
      cursor = std::max (cursor, b);
      if (cursor >= end) break;
    }
  if (cursor < end) ranges.emplace_back (cursor, end - cursor);
  uint32_t added = 0;
  for (auto range : ranges) added += range.second;
  if (added > Available ()) return false;
  for (auto range : ranges)
    {
      auto item = new QuicStreamRxItem ();
      item->m_offset = range.first;
      item->m_packet = p->CreateFragment (range.first - sub.GetOffset (), range.second);
      item->m_fin = sub.IsStreamFin ();
      auto position = std::lower_bound (m_streamRecvList.begin (), m_streamRecvList.end (),
        item->m_offset, [](auto current, uint64_t offset) { return current->m_offset < offset; });
      m_streamRecvList.insert (position, item);
    }
  m_numBytesInBuffer += added;
  if (sub.IsStreamFin ()) { m_finalSize = end; m_recvFin = true; }
  return true;
}

Ptr<Packet>
QuicStreamRxBuffer::Extract (uint32_t maxSize)
{
  NS_LOG_FUNCTION (this << maxSize);

  uint32_t extractSize = std::min (maxSize, m_numBytesInBuffer);
  NS_LOG_INFO (
    "Requested to extract " << extractSize << " bytes from QuicStreamRxBuffer of size = " << m_numBytesInBuffer);

  if (extractSize == 0)
    {
      return 0;
    }

  Ptr<Packet> outPkt = Create<Packet> ();

  QuicStreamRxPacketList::iterator it = m_streamRecvList.begin ();

  while (extractSize > 0 && !m_streamRecvList.empty ()
         && it != m_streamRecvList.end ())
    {
      it = m_streamRecvList.begin ();
      Ptr<Packet> currentPacket = (*it)->m_packet;

      if (currentPacket->GetSize () <= extractSize)   // Merge
        {

          outPkt->AddAtEnd (currentPacket);
          auto extracted = *it;
          m_streamRecvList.erase (it);
          delete extracted;

          m_numBytesInBuffer -= currentPacket->GetSize ();
          extractSize -= currentPacket->GetSize ();

          continue;
        }
      else
        {
          break;
        }

      it++;
    }

  if (outPkt->GetSize () == 0)
    {
      NS_LOG_INFO ("Nothing extracted.");
      return 0;
    }

  return outPkt;
}

std::pair<uint64_t, uint64_t>
QuicStreamRxBuffer::GetDeliverable (uint64_t currRecvOffset)
{
  NS_LOG_FUNCTION (this);
  uint64_t cursor = currRecvOffset;
  uint64_t length = 0;
  for (auto it = m_streamRecvList.begin (); it != m_streamRecvList.end ();)
    {
      auto item = *it;
      uint64_t end = item->m_offset + item->m_packet->GetSize ();
      if (end <= cursor)
        {
          m_numBytesInBuffer -= item->m_packet->GetSize ();
          delete item;
          it = m_streamRecvList.erase (it);
          continue;
        }
      if (item->m_offset < cursor)
        {
          uint32_t overlap = static_cast<uint32_t> (cursor - item->m_offset);
          item->m_packet->RemoveAtStart (overlap);
          item->m_offset = cursor;
          m_numBytesInBuffer -= overlap;
        }
      if (item->m_offset != cursor) break;
      length += item->m_packet->GetSize ();
      cursor += item->m_packet->GetSize ();
      ++it;
    }
  return std::make_pair (currRecvOffset, length);
}

uint32_t
QuicStreamRxBuffer::Size (void) const
{
  NS_LOG_FUNCTION (this);

  // uint32_t inFlight = 0;
  // for (auto recv_it = m_streamRecvList.begin (); recv_it != m_streamRecvList.end () and !m_streamRecvList.empty (); ++recv_it)
  //   {
  //     inFlight += (*recv_it)->m_packet->GetSize ();
  //   }

  return m_numBytesInBuffer;
}

uint32_t
QuicStreamRxBuffer::Available (void) const
{
  return m_maxBuffer - m_numBytesInBuffer;
}

uint32_t
QuicStreamRxBuffer::GetMaxBufferSize (void) const
{
  return m_maxBuffer;
}

void
QuicStreamRxBuffer::SetMaxBufferSize (uint32_t s)
{
  m_maxBuffer = s;
}

uint32_t
QuicStreamRxBuffer::GetFinalSize () const
{
  return m_finalSize;
}

void
QuicStreamRxBuffer::Print (std::ostream & os) const
{
  NS_LOG_FUNCTION (this);
  QuicStreamRxBuffer::QuicStreamRxPacketList::const_iterator it;
  std::stringstream ss;
  std::stringstream as;

  for (it = m_streamRecvList.begin (); it != m_streamRecvList.end (); ++it)
    {
      (*it)->Print (ss);
    }

  os << "Stream Recv list: \n" << ss.str () << "\n\nCurrent Status: "
     << "\nNumber of receptions = " << m_streamRecvList.size ()
     << "\nReceived Size = " << m_numBytesInBuffer;
  if (m_recvFin)
    {
      os << "\nFinal Size = " << m_finalSize;

    }

}

} //namepsace ns3
