use std::env;
use std::fs::File;
use std::io::{self, BufReader, Read};
use std::process;
use std::time::Instant;

const BATCH_MAGIC: &[u8] = b"OCNBATCH1";
const PACKET_MAGIC: &[u8] = b"OCN2";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Codec {
    Gorilla,
    Chimp,
}

impl Codec {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "gorilla" => Ok(Self::Gorilla),
            "chimp" => Ok(Self::Chimp),
            _ => Err(format!("unsupported codec: {value}")),
        }
    }

    fn id(self) -> u8 {
        match self {
            Self::Gorilla => 1,
            Self::Chimp => 2,
        }
    }

    fn from_id(value: u8) -> Result<Self, String> {
        match value {
            1 => Ok(Self::Gorilla),
            2 => Ok(Self::Chimp),
            _ => Err(format!("unsupported codec id: {value}")),
        }
    }
}

struct RawPacket {
    timestamps: Vec<i64>,
    columns: Vec<Vec<u64>>,
}

struct BitWriter {
    data: Vec<u8>,
    current: u8,
    used: u8,
}

impl BitWriter {
    fn new() -> Self {
        Self {
            data: Vec::new(),
            current: 0,
            used: 0,
        }
    }

    fn write_bit(&mut self, bit: bool) {
        if bit {
            self.current |= 1 << (7 - self.used);
        }
        self.used += 1;
        if self.used == 8 {
            self.data.push(self.current);
            self.current = 0;
            self.used = 0;
        }
    }

    fn write_bits(&mut self, value: u64, width: u32) {
        for shift in (0..width).rev() {
            self.write_bit(((value >> shift) & 1) != 0);
        }
    }

    fn write_signed(&mut self, value: i64, width: u32) {
        let bits = if width == 64 {
            value as u64
        } else {
            let mask = (1_i128 << width) - 1;
            ((value as i128) & mask) as u64
        };
        self.write_bits(bits, width);
    }

    fn finish(mut self) -> Vec<u8> {
        if self.used != 0 {
            self.data.push(self.current);
        }
        self.data
    }
}

struct BitReader<'a> {
    data: &'a [u8],
    index: usize,
    used: u8,
}

impl<'a> BitReader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self {
            data,
            index: 0,
            used: 0,
        }
    }

    fn read_bit(&mut self) -> Result<bool, String> {
        if self.index >= self.data.len() {
            return Err("bitstream ended unexpectedly".to_string());
        }
        let bit = ((self.data[self.index] >> (7 - self.used)) & 1) != 0;
        self.used += 1;
        if self.used == 8 {
            self.index += 1;
            self.used = 0;
        }
        Ok(bit)
    }

    fn read_bits(&mut self, width: u32) -> Result<u64, String> {
        let mut value = 0_u64;
        for _ in 0..width {
            value = (value << 1) | u64::from(self.read_bit()?);
        }
        Ok(value)
    }

    fn read_signed(&mut self, width: u32) -> Result<i64, String> {
        let value = self.read_bits(width)?;
        if width == 64 {
            Ok(value as i64)
        } else {
            let sign_bit = 1_u64 << (width - 1);
            if (value & sign_bit) != 0 {
                Ok((value as i64) - (1_i64 << width))
            } else {
                Ok(value as i64)
            }
        }
    }
}

fn encode_timestamps_gorilla(timestamps: &[i64]) -> Vec<u8> {
    let mut writer = BitWriter::new();
    if timestamps.is_empty() {
        return writer.finish();
    }
    writer.write_signed(timestamps[0], 64);
    if timestamps.len() == 1 {
        return writer.finish();
    }
    let mut previous = timestamps[0];
    let mut delta = timestamps[1] - previous;
    writer.write_signed(delta, 64);
    previous = timestamps[1];
    let mut previous_delta = delta;
    for &timestamp in &timestamps[2..] {
        delta = timestamp - previous;
        let delta_of_delta = delta - previous_delta;
        if delta_of_delta == 0 {
            writer.write_bit(false);
        } else if (-64..=63).contains(&delta_of_delta) {
            writer.write_bits(0b10, 2);
            writer.write_signed(delta_of_delta, 7);
        } else if (-256..=255).contains(&delta_of_delta) {
            writer.write_bits(0b110, 3);
            writer.write_signed(delta_of_delta, 9);
        } else if (-2048..=2047).contains(&delta_of_delta) {
            writer.write_bits(0b1110, 4);
            writer.write_signed(delta_of_delta, 12);
        } else {
            writer.write_bits(0b1111, 4);
            writer.write_signed(delta_of_delta, 32);
        }
        previous = timestamp;
        previous_delta = delta;
    }
    writer.finish()
}

fn decode_timestamps_gorilla(data: &[u8], count: usize) -> Result<Vec<i64>, String> {
    if count == 0 {
        return Ok(Vec::new());
    }
    let mut reader = BitReader::new(data);
    let first = reader.read_signed(64)?;
    let mut timestamps = Vec::with_capacity(count);
    timestamps.push(first);
    if count == 1 {
        return Ok(timestamps);
    }
    let mut delta = reader.read_signed(64)?;
    let mut previous = first + delta;
    timestamps.push(previous);
    let mut previous_delta = delta;
    while timestamps.len() < count {
        let first_control = reader.read_bit()?;
        let delta_of_delta = if !first_control {
            0
        } else if !reader.read_bit()? {
            reader.read_signed(7)?
        } else if !reader.read_bit()? {
            reader.read_signed(9)?
        } else if !reader.read_bit()? {
            reader.read_signed(12)?
        } else {
            reader.read_signed(32)?
        };
        delta = previous_delta + delta_of_delta;
        previous += delta;
        previous_delta = delta;
        timestamps.push(previous);
    }
    Ok(timestamps)
}

fn encode_values_gorilla(values: &[u64]) -> Vec<u8> {
    let mut writer = BitWriter::new();
    if values.is_empty() {
        return writer.finish();
    }
    writer.write_bits(values[0], 64);
    let mut previous = values[0];
    let mut stored_leading = 64_u32;
    let mut stored_trailing = 0_u32;
    for &current in &values[1..] {
        let xor = current ^ previous;
        if xor == 0 {
            writer.write_bit(false);
        } else {
            writer.write_bit(true);
            let leading = xor.leading_zeros().min(31);
            let trailing = xor.trailing_zeros();
            if stored_leading != 64 && leading >= stored_leading && trailing >= stored_trailing {
                writer.write_bit(false);
                let significant = 64 - stored_leading - stored_trailing;
                writer.write_bits(xor >> stored_trailing, significant);
            } else {
                writer.write_bit(true);
                let significant = 64 - leading - trailing;
                writer.write_bits(u64::from(leading), 5);
                writer.write_bits(if significant == 64 { 0 } else { u64::from(significant) }, 6);
                writer.write_bits(xor >> trailing, significant);
                stored_leading = leading;
                stored_trailing = trailing;
            }
        }
        previous = current;
    }
    writer.finish()
}

fn decode_values_gorilla(data: &[u8], count: usize) -> Result<Vec<u64>, String> {
    if count == 0 {
        return Ok(Vec::new());
    }
    let mut reader = BitReader::new(data);
    let mut previous = reader.read_bits(64)?;
    let mut values = Vec::with_capacity(count);
    values.push(previous);
    let mut stored_leading = 64_u32;
    let mut stored_trailing = 0_u32;
    while values.len() < count {
        let current = if !reader.read_bit()? {
            previous
        } else {
            let reuse_window = !reader.read_bit()?;
            let (leading, trailing, significant) = if reuse_window {
                let significant = 64 - stored_leading - stored_trailing;
                (stored_leading, stored_trailing, significant)
            } else {
                let leading = reader.read_bits(5)? as u32;
                let mut significant = reader.read_bits(6)? as u32;
                if significant == 0 {
                    significant = 64;
                }
                let trailing = 64 - leading - significant;
                stored_leading = leading;
                stored_trailing = trailing;
                (leading, trailing, significant)
            };
            let _ = leading;
            let meaningful = reader.read_bits(significant)?;
            previous ^ (meaningful << trailing)
        };
        values.push(current);
        previous = current;
    }
    Ok(values)
}

fn encode_values_chimp(values: &[u64]) -> Vec<u8> {
    let mut writer = BitWriter::new();
    if values.is_empty() {
        return writer.finish();
    }
    writer.write_bits(values[0], 64);
    let mut window = Vec::with_capacity(128);
    window.push(values[0]);
    for &current in &values[1..] {
        let mut best_offset = 0_usize;
        let mut best_xor = current ^ *window.last().expect("window is not empty");
        let mut best_score = 64 - best_xor.leading_zeros();
        let max_offset = window.len().min(128);
        for offset in 0..max_offset {
            let reference = window[window.len() - 1 - offset];
            let xor = current ^ reference;
            let score = 64 - xor.leading_zeros();
            if score < best_score {
                best_offset = offset;
                best_xor = xor;
                best_score = score;
                if score == 0 {
                    break;
                }
            }
        }
        writer.write_bits(best_offset as u64, 7);
        if best_xor == 0 {
            writer.write_bit(false);
        } else {
            writer.write_bit(true);
            let leading = best_xor.leading_zeros();
            let trailing = best_xor.trailing_zeros();
            let significant = 64 - leading - trailing;
            writer.write_bits(u64::from(leading), 6);
            writer.write_bits(if significant == 64 { 0 } else { u64::from(significant) }, 6);
            writer.write_bits(best_xor >> trailing, significant);
        }
        window.push(current);
        if window.len() > 128 {
            window.remove(0);
        }
    }
    writer.finish()
}

fn decode_values_chimp(data: &[u8], count: usize) -> Result<Vec<u64>, String> {
    if count == 0 {
        return Ok(Vec::new());
    }
    let mut reader = BitReader::new(data);
    let first = reader.read_bits(64)?;
    let mut values = Vec::with_capacity(count);
    values.push(first);
    let mut window = Vec::with_capacity(128);
    window.push(first);
    while values.len() < count {
        let offset = reader.read_bits(7)? as usize;
        if offset >= window.len() {
            return Err(format!("invalid chimp offset {offset} for window {}", window.len()));
        }
        let has_xor = reader.read_bit()?;
        let reference = window[window.len() - 1 - offset];
        let current = if has_xor {
            let leading = reader.read_bits(6)? as u32;
            let mut significant = reader.read_bits(6)? as u32;
            if significant == 0 {
                significant = 64;
            }
            let trailing = 64 - leading - significant;
            let meaningful = reader.read_bits(significant)?;
            reference ^ (meaningful << trailing)
        } else {
            reference
        };
        values.push(current);
        window.push(current);
        if window.len() > 128 {
            window.remove(0);
        }
    }
    Ok(values)
}

fn put_u32(output: &mut Vec<u8>, value: usize) {
    output.extend_from_slice(&(value as u32).to_be_bytes());
}

fn encode_packet(packet: &RawPacket, codec: Codec) -> Vec<u8> {
    let mut output = Vec::new();
    output.extend_from_slice(PACKET_MAGIC);
    output.push(codec.id());
    put_u32(&mut output, packet.timestamps.len());
    put_u32(&mut output, packet.columns.len());

    let timestamp_data = encode_timestamps_gorilla(&packet.timestamps);
    put_u32(&mut output, timestamp_data.len());
    output.extend_from_slice(&timestamp_data);

    for column in &packet.columns {
        let value_data = match codec {
            Codec::Gorilla => encode_values_gorilla(column),
            Codec::Chimp => encode_values_chimp(column),
        };
        put_u32(&mut output, value_data.len());
        output.extend_from_slice(&value_data);
    }
    output
}

fn read_u32_from_slice(data: &[u8], offset: &mut usize) -> Result<usize, String> {
    let end = *offset + 4;
    if end > data.len() {
        return Err("truncated u32 field".to_string());
    }
    let value = u32::from_be_bytes(data[*offset..end].try_into().unwrap()) as usize;
    *offset = end;
    Ok(value)
}

fn read_bytes<'a>(data: &'a [u8], offset: &mut usize, len: usize) -> Result<&'a [u8], String> {
    let end = *offset + len;
    if end > data.len() {
        return Err("truncated byte field".to_string());
    }
    let value = &data[*offset..end];
    *offset = end;
    Ok(value)
}

fn decode_packet(data: &[u8]) -> Result<RawPacket, String> {
    let mut offset = 0_usize;
    if read_bytes(data, &mut offset, PACKET_MAGIC.len())? != PACKET_MAGIC {
        return Err("invalid packet magic".to_string());
    }
    let codec_id = *read_bytes(data, &mut offset, 1)?
        .first()
        .ok_or_else(|| "missing codec id".to_string())?;
    let codec = Codec::from_id(codec_id)?;
    let row_count = read_u32_from_slice(data, &mut offset)?;
    let col_count = read_u32_from_slice(data, &mut offset)?;
    let timestamp_len = read_u32_from_slice(data, &mut offset)?;
    let timestamp_data = read_bytes(data, &mut offset, timestamp_len)?;
    let timestamps = decode_timestamps_gorilla(timestamp_data, row_count)?;

    let mut columns = Vec::with_capacity(col_count);
    for _ in 0..col_count {
        let value_len = read_u32_from_slice(data, &mut offset)?;
        let value_data = read_bytes(data, &mut offset, value_len)?;
        let values = match codec {
            Codec::Gorilla => decode_values_gorilla(value_data, row_count)?,
            Codec::Chimp => decode_values_chimp(value_data, row_count)?,
        };
        columns.push(values);
    }
    Ok(RawPacket { timestamps, columns })
}

fn packets_equal(left: &RawPacket, right: &RawPacket) -> bool {
    left.timestamps == right.timestamps && left.columns == right.columns
}

fn read_exact_array<const N: usize, R: Read>(reader: &mut R) -> io::Result<[u8; N]> {
    let mut buffer = [0_u8; N];
    reader.read_exact(&mut buffer)?;
    Ok(buffer)
}

fn read_u32<R: Read>(reader: &mut R) -> io::Result<usize> {
    Ok(u32::from_be_bytes(read_exact_array::<4, _>(reader)?) as usize)
}

fn read_i64<R: Read>(reader: &mut R) -> io::Result<i64> {
    Ok(i64::from_be_bytes(read_exact_array::<8, _>(reader)?))
}

fn read_u64<R: Read>(reader: &mut R) -> io::Result<u64> {
    Ok(u64::from_be_bytes(read_exact_array::<8, _>(reader)?))
}

fn load_batch(path: &str) -> Result<Vec<RawPacket>, String> {
    let file = File::open(path).map_err(|error| format!("failed to open input: {error}"))?;
    let mut reader = BufReader::new(file);
    let mut magic = vec![0_u8; BATCH_MAGIC.len()];
    reader
        .read_exact(&mut magic)
        .map_err(|error| format!("failed to read batch magic: {error}"))?;
    if magic != BATCH_MAGIC {
        return Err("invalid batch magic".to_string());
    }
    let packet_count = read_u32(&mut reader).map_err(|error| format!("failed to read packet count: {error}"))?;
    let mut packets = Vec::with_capacity(packet_count);
    for packet_index in 0..packet_count {
        let row_count = read_u32(&mut reader)
            .map_err(|error| format!("failed to read row count for packet {packet_index}: {error}"))?;
        let col_count = read_u32(&mut reader)
            .map_err(|error| format!("failed to read column count for packet {packet_index}: {error}"))?;
        let mut timestamps = Vec::with_capacity(row_count);
        for _ in 0..row_count {
            timestamps.push(
                read_i64(&mut reader)
                    .map_err(|error| format!("failed to read timestamp for packet {packet_index}: {error}"))?,
            );
        }
        let mut columns = Vec::with_capacity(col_count);
        for column_index in 0..col_count {
            let mut values = Vec::with_capacity(row_count);
            for _ in 0..row_count {
                values.push(
                    read_u64(&mut reader).map_err(|error| {
                        format!("failed to read value for packet {packet_index}, column {column_index}: {error}")
                    })?,
                );
            }
            columns.push(values);
        }
        packets.push(RawPacket { timestamps, columns });
    }
    Ok(packets)
}

fn parse_args() -> Result<(Codec, String), String> {
    let mut codec = None;
    let mut input = None;
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--codec" => {
                let value = args.next().ok_or_else(|| "--codec needs a value".to_string())?;
                codec = Some(Codec::parse(&value)?);
            }
            "--input" => {
                input = Some(args.next().ok_or_else(|| "--input needs a value".to_string())?);
            }
            "--help" | "-h" => {
                println!("Usage: ocean_numeric_codec --codec <gorilla|chimp> --input <batch.bin>");
                process::exit(0);
            }
            _ => return Err(format!("unknown argument: {arg}")),
        }
    }
    let codec = codec.ok_or_else(|| "missing --codec".to_string())?;
    let input = input.ok_or_else(|| "missing --input".to_string())?;
    Ok((codec, input))
}

fn run() -> Result<(), String> {
    let (codec, input) = parse_args()?;
    let packets = load_batch(&input)?;

    let compression_start = Instant::now();
    let compressed_packets: Vec<Vec<u8>> = packets.iter().map(|packet| encode_packet(packet, codec)).collect();
    let compression_time_ms = compression_start.elapsed().as_secs_f64() * 1000.0;
    let compressed_size_bytes: usize = compressed_packets.iter().map(Vec::len).sum();

    let decompression_start = Instant::now();
    let mut integrity_ok = true;
    for (expected, compressed) in packets.iter().zip(compressed_packets.iter()) {
        let restored = decode_packet(compressed)?;
        if !packets_equal(expected, &restored) {
            integrity_ok = false;
            break;
        }
    }
    let decompression_time_ms = decompression_start.elapsed().as_secs_f64() * 1000.0;

    println!(
        "{{\"status\":\"ok\",\"compressed_size_bytes\":{},\"compression_time_ms\":{:.9},\"decompression_time_ms\":{:.9},\"integrity\":\"{}\",\"valid_packets\":{}}}",
        compressed_size_bytes,
        compression_time_ms,
        decompression_time_ms,
        if integrity_ok { "pass" } else { "fail" },
        packets.len()
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        process::exit(1);
    }
}
