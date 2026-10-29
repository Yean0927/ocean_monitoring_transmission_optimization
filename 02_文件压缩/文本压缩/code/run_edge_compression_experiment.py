
# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT / 'data/图片文件'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT / '原始实验留档/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Run per-packet compression experiments for ocean observation data.

import argparse
import csv
import gzip
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOCAL_PACKAGES = ROOT / "python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))


ALGORITHMS = ["gorilla", "chimp", "gzip", "parquet_zstd", "parquet_snappy"]
DEFAULT_PACKET_SIZES = [512, 1448, 4096]
DEFAULT_BANDWIDTHS_MBPS = [2.0, 4.0, 10.0]
TEXT_EXTENSIONS = {".txt", ".log"}
NATIVE_CODEC_BIN = (
    ROOT
    / "native_codecs"
    / "ocean_numeric_codec"
    / "target"
    / "release"
    / ("ocean_numeric_codec.exe" if os.name == "nt" else "ocean_numeric_codec")
)


@dataclass
class Record:
    raw: bytes
    text: str
    source_file: str
    line_no: int


@dataclass
class Dataset:
    dataset_id: str
    kind: str
    records: list
    source_files: list
    raw_size_bytes: int
    encoding: str


@dataclass
class Packet:
    packet_id: int
    records: list

    @property
    def raw(self):
        return b"".join(record.raw for record in self.records)


@dataclass
class NumericPacket:
    timestamps: list
    columns: list
    values: dict


class BitWriter:
    def __init__(self):
        self.data = bytearray()
        self.current = 0
        self.used = 0

    def write_bit(self, bit):
        if bit:
            self.current |= 1 << (7 - self.used)
        self.used += 1
        if self.used == 8:
            self.data.append(self.current)
            self.current = 0
            self.used = 0

    def write_bits(self, value, width):
        if width <= 0:
            return
        for shift in range(width - 1, -1, -1):
            self.write_bit((value >> shift) & 1)

    def write_signed(self, value, width):
        if value < 0:
            value += 1 << width
        self.write_bits(value, width)

    def finish(self):
        if self.used:
            self.data.append(self.current)
            self.current = 0
            self.used = 0
        return bytes(self.data)


class BitReader:
    def __init__(self, data):
        self.data = data
        self.index = 0
        self.used = 0

    def read_bit(self):
        if self.index >= len(self.data):
            raise EOFError("bitstream ended unexpectedly")
        bit = (self.data[self.index] >> (7 - self.used)) & 1
        self.used += 1
        if self.used == 8:
            self.index += 1
            self.used = 0
        return bit

    def read_bits(self, width):
        value = 0
        for _ in range(width):
            value = (value << 1) | self.read_bit()
        return value

    def read_signed(self, width):
        value = self.read_bits(width)
        sign_bit = 1 << (width - 1)
        if value & sign_bit:
            value -= 1 << width
        return value


def float_to_bits(value):
    return struct.unpack(">Q", struct.pack(">d", float(value)))[0]


def bits_to_float(value):
    return struct.unpack(">d", struct.pack(">Q", value))[0]


def leading_zeros(value):
    return 64 - value.bit_length() if value else 64


def trailing_zeros(value):
    if value == 0:
        return 64
    return (value & -value).bit_length() - 1


def pack_u32(value):
    return struct.pack(">I", value)


def unpack_u32(stream):
    data = stream.read(4)
    if len(data) != 4:
        raise EOFError("missing uint32")
    return struct.unpack(">I", data)[0]


def encode_timestamps_gorilla(timestamps):
    writer = BitWriter()
    count = len(timestamps)
    if count == 0:
        return writer.finish()
    writer.write_signed(int(timestamps[0]), 64)
    if count == 1:
        return writer.finish()
    previous = int(timestamps[0])
    delta = int(timestamps[1]) - previous
    writer.write_signed(delta, 64)
    previous = int(timestamps[1])
    previous_delta = delta
    for timestamp in timestamps[2:]:
        timestamp = int(timestamp)
        delta = timestamp - previous
        delta_of_delta = delta - previous_delta
        if delta_of_delta == 0:
            writer.write_bit(0)
        elif -64 <= delta_of_delta <= 63:
            writer.write_bits(0b10, 2)
            writer.write_signed(delta_of_delta, 7)
        elif -256 <= delta_of_delta <= 255:
            writer.write_bits(0b110, 3)
            writer.write_signed(delta_of_delta, 9)
        elif -2048 <= delta_of_delta <= 2047:
            writer.write_bits(0b1110, 4)
            writer.write_signed(delta_of_delta, 12)
        else:
            writer.write_bits(0b1111, 4)
            writer.write_signed(delta_of_delta, 32)
        previous = timestamp
        previous_delta = delta
    return writer.finish()


def decode_timestamps_gorilla(data, count):
    if count == 0:
        return []
    reader = BitReader(data)
    first = reader.read_signed(64)
    timestamps = [first]
    if count == 1:
        return timestamps
    delta = reader.read_signed(64)
    second = first + delta
    timestamps.append(second)
    previous = second
    previous_delta = delta
    while len(timestamps) < count:
        first_control = reader.read_bit()
        if first_control == 0:
            delta_of_delta = 0
        else:
            second_control = reader.read_bit()
            if second_control == 0:
                delta_of_delta = reader.read_signed(7)
            else:
                third_control = reader.read_bit()
                if third_control == 0:
                    delta_of_delta = reader.read_signed(9)
                else:
                    fourth_control = reader.read_bit()
                    if fourth_control == 0:
                        delta_of_delta = reader.read_signed(12)
                    else:
                        delta_of_delta = reader.read_signed(32)
        delta = previous_delta + delta_of_delta
        previous = previous + delta
        previous_delta = delta
        timestamps.append(previous)
    return timestamps


def encode_values_gorilla(values):
    writer = BitWriter()
    if not values:
        return writer.finish()
    bits = [float_to_bits(value) for value in values]
    writer.write_bits(bits[0], 64)
    previous = bits[0]
    stored_leading = 64
    stored_trailing = 0
    for current in bits[1:]:
        xor = current ^ previous
        if xor == 0:
            writer.write_bit(0)
        else:
            writer.write_bit(1)
            leading = min(leading_zeros(xor), 31)
            trailing = trailing_zeros(xor)
            if stored_leading != 64 and leading >= stored_leading and trailing >= stored_trailing:
                writer.write_bit(0)
                significant = 64 - stored_leading - stored_trailing
                writer.write_bits(xor >> stored_trailing, significant)
            else:
                writer.write_bit(1)
                significant = 64 - leading - trailing
                writer.write_bits(leading, 5)
                writer.write_bits(0 if significant == 64 else significant, 6)
                writer.write_bits(xor >> trailing, significant)
                stored_leading = leading
                stored_trailing = trailing
        previous = current
    return writer.finish()


def decode_values_gorilla(data, count):
    if count == 0:
        return []
    reader = BitReader(data)
    previous = reader.read_bits(64)
    values = [bits_to_float(previous)]
    stored_leading = 64
    stored_trailing = 0
    while len(values) < count:
        control = reader.read_bit()
        if control == 0:
            current = previous
        else:
            reuse_window = reader.read_bit() == 0
            if reuse_window:
                leading = stored_leading
                trailing = stored_trailing
                significant = 64 - leading - trailing
            else:
                leading = reader.read_bits(5)
                significant = reader.read_bits(6)
                if significant == 0:
                    significant = 64
                trailing = 64 - leading - significant
                stored_leading = leading
                stored_trailing = trailing
            meaningful = reader.read_bits(significant)
            current = previous ^ (meaningful << trailing)
        values.append(bits_to_float(current))
        previous = current
    return values


def encode_values_chimp(values):
    writer = BitWriter()
    if not values:
        return writer.finish()
    bits = [float_to_bits(value) for value in values]
    writer.write_bits(bits[0], 64)
    window = [bits[0]]
    for current in bits[1:]:
        best_offset = 0
        best_xor = current ^ window[-1]
        best_score = best_xor.bit_length()
        max_offset = min(len(window), 128)
        for offset in range(max_offset):
            reference = window[-1 - offset]
            xor = current ^ reference
            score = xor.bit_length()
            if score < best_score:
                best_offset = offset
                best_xor = xor
                best_score = score
                if score == 0:
                    break
        writer.write_bits(best_offset, 7)
        if best_xor == 0:
            writer.write_bit(0)
        else:
            writer.write_bit(1)
            leading = leading_zeros(best_xor)
            trailing = trailing_zeros(best_xor)
            significant = 64 - leading - trailing
            writer.write_bits(leading, 6)
            writer.write_bits(0 if significant == 64 else significant, 6)
            writer.write_bits(best_xor >> trailing, significant)
        window.append(current)
        if len(window) > 128:
            window.pop(0)
    return writer.finish()


def decode_values_chimp(data, count):
    if count == 0:
        return []
    reader = BitReader(data)
    first = reader.read_bits(64)
    values = [bits_to_float(first)]
    window = [first]
    while len(values) < count:
        offset = reader.read_bits(7)
        has_xor = reader.read_bit()
        reference = window[-1 - offset]
        if has_xor:
            leading = reader.read_bits(6)
            significant = reader.read_bits(6)
            if significant == 0:
                significant = 64
            trailing = 64 - leading - significant
            meaningful = reader.read_bits(significant)
            current = reference ^ (meaningful << trailing)
        else:
            current = reference
        values.append(bits_to_float(current))
        window.append(current)
        if len(window) > 128:
            window.pop(0)
    return values


def encode_numeric_packet(packet, codec):
    if codec == "gorilla":
        encode_values = encode_values_gorilla
    elif codec == "chimp":
        encode_values = encode_values_chimp
    else:
        raise ValueError(f"unknown numeric codec: {codec}")
    header = {
        "codec": codec,
        "row_count": len(packet.timestamps),
        "columns": packet.columns,
        "timestamp_codec": "gorilla_delta_of_delta",
        "value_codec": "gorilla_xor" if codec == "gorilla" else "chimp_style_window_xor",
    }
    header_bytes = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    chunks = [b"OCEAN_NUM1", pack_u32(len(header_bytes)), header_bytes]
    timestamp_data = encode_timestamps_gorilla(packet.timestamps)
    chunks.append(pack_u32(len(timestamp_data)))
    chunks.append(timestamp_data)
    for column in packet.columns:
        value_data = encode_values(packet.values[column])
        chunks.append(pack_u32(len(value_data)))
        chunks.append(value_data)
    return b"".join(chunks)


def decode_numeric_packet(data):
    stream = io.BytesIO(data)
    magic = stream.read(len(b"OCEAN_NUM1"))
    if magic != b"OCEAN_NUM1":
        raise ValueError("invalid numeric packet magic")
    header_len = unpack_u32(stream)
    header = json.loads(stream.read(header_len).decode("utf-8"))
    count = int(header["row_count"])
    timestamp_len = unpack_u32(stream)
    timestamps = decode_timestamps_gorilla(stream.read(timestamp_len), count)
    codec = header["codec"]
    if codec == "gorilla":
        decode_values = decode_values_gorilla
    elif codec == "chimp":
        decode_values = decode_values_chimp
    else:
        raise ValueError(f"unknown numeric codec: {codec}")
    values = {}
    for column in header["columns"]:
        value_len = unpack_u32(stream)
        values[column] = decode_values(stream.read(value_len), count)
    return NumericPacket(timestamps=timestamps, columns=header["columns"], values=values)


def parse_list(value, caster):
    if isinstance(value, (list, tuple)):
        return list(value)
    result = []
    for item in str(value).split(","):
        item = item.strip()
        if item:
            result.append(caster(item))
    return result


def detect_encoding(raw):
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ["utf-8", "gb18030", "gbk"]:
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            pass
    return "latin1"


def body_encoding_for(encoding, raw):
    if encoding == "utf-16":
        if raw.startswith(b"\xfe\xff"):
            return "utf-16-be", b"\xfe\xff"
        return "utf-16-le", b"\xff\xfe" if raw.startswith(b"\xff\xfe") else b""
    if encoding == "utf-8-sig":
        return "utf-8", b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    return encoding, b""


def split_records(path):
    raw = path.read_bytes()
    encoding = detect_encoding(raw)
    text = raw.decode(encoding, errors="replace")
    lines = text.splitlines(keepends=True)
    body_encoding, bom = body_encoding_for(encoding, raw)
    records = []
    for index, line in enumerate(lines, start=1):
        line_raw = line.encode(body_encoding, errors="replace")
        if index == 1 and bom and not line_raw.startswith(bom):
            line_raw = bom + line_raw
        records.append(Record(raw=line_raw, text=line, source_file=path.name, line_no=index))
    reconstructed = b"".join(record.raw for record in records)
    if reconstructed != raw:
        records = []
        for index, line_raw in enumerate(raw.splitlines(keepends=True), start=1):
            records.append(
                Record(
                    raw=line_raw,
                    text=line_raw.decode(encoding, errors="replace"),
                    source_file=path.name,
                    line_no=index,
                )
            )
    return records, encoding, len(raw)


def find_one(input_dir, predicate):
    matches = sorted(path for path in input_dir.iterdir() if path.is_file() and predicate(path.name))
    return matches[0] if matches else None


def load_single_dataset(dataset_id, kind, path):
    records, encoding, raw_size = split_records(path)
    return Dataset(
        dataset_id=dataset_id,
        kind=kind,
        records=records,
        source_files=[path.name],
        raw_size_bytes=raw_size,
        encoding=encoding,
    )


def discover_datasets(input_dir):
    input_dir = Path(input_dir)
    datasets = []
    big_weather = find_one(input_dir, lambda name: "大浮标气象数据" in name and name.endswith(".txt"))
    weather = find_one(input_dir, lambda name: name == "气象数据.txt")
    wave = find_one(input_dir, lambda name: "波浪传感器" in name and name.endswith(".txt"))
    logs = sorted(path for path in input_dir.iterdir() if path.is_file() and "海流log-info" in path.name and path.suffix == ".log")

    if big_weather:
        datasets.append(load_single_dataset("D1_big_buoy_weather", "big_weather_csv", big_weather))
    if weather:
        datasets.append(load_single_dataset("D2_weather_utf16", "weather_tsv", weather))
    if wave:
        datasets.append(load_single_dataset("D3_wave_sensor", "wave_sensor_tsv", wave))
    if logs:
        records = []
        source_files = []
        raw_size = 0
        encodings = []
        for path in logs:
            file_records, encoding, size = split_records(path)
            records.extend(file_records)
            source_files.append(path.name)
            raw_size += size
            encodings.append(encoding)
        datasets.append(
            Dataset(
                dataset_id="D4_ocean_current_log",
                kind="ocean_current_log",
                records=records,
                source_files=source_files,
                raw_size_bytes=raw_size,
                encoding=",".join(sorted(set(encodings))),
            )
        )
    return datasets


def build_packets(records, target_size):
    packets = []
    current = []
    current_size = 0
    for record in records:
        size = len(record.raw)
        if current and current_size + size > target_size:
            packets.append(Packet(packet_id=len(packets), records=current))
            current = []
            current_size = 0
        current.append(record)
        current_size += size
    if current:
        packets.append(Packet(packet_id=len(packets), records=current))
    return packets


def clean_cell(value):
    return value.replace("\ufeff", "").replace("\x00", "").strip()


def split_delimited(line, delimiter):
    return [clean_cell(cell) for cell in line.strip("\r\n").split(delimiter)]


def parse_datetime_ms(value):
    value = clean_cell(value)
    if not value:
        return None
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ]
    for fmt in formats:
        try:
            return int(datetime.strptime(value, fmt).timestamp() * 1000)
        except ValueError:
            pass
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?(?:\.(\d+))?$", value)
    if not match:
        return None
    year, month, day, hour, minute, second, fraction = match.groups()
    microsecond = int((fraction or "0")[:6].ljust(6, "0"))
    dt = datetime(
        int(year),
        int(month),
        int(day),
        int(hour),
        int(minute),
        int(second or 0),
        microsecond,
    )
    return int(dt.timestamp() * 1000)


def parse_float(value):
    value = clean_cell(value)
    if value == "":
        return math.nan
    value = value.replace("%", "").replace("dB", "").replace("°", "")
    try:
        return float(value)
    except ValueError:
        return math.nan


def is_nan(value):
    return isinstance(value, float) and math.isnan(value)


def numeric_packet_from_records(dataset, packet):
    timestamps = []
    rows = []
    if dataset.kind == "big_weather_csv":
        columns = [
            "air_temperature",
            "atmosphere",
            "wind_speed",
            "wind_direction",
            "maximum_instantaneous_air_speed",
            "wind_direction_at_maximum_instantaneous_wind_speed",
            "relative_humidity",
            "rainfall",
            "heading",
            "pitch",
            "roll",
        ]
        for record in packet.records:
            cells = split_delimited(record.text, ",")
            if not cells or clean_cell(cells[0]).lower() == "time":
                continue
            timestamp = parse_datetime_ms(cells[0])
            if timestamp is None or len(cells) < 2:
                continue
            values = [parse_float(cells[index]) if index < len(cells) else math.nan for index in range(1, 12)]
            timestamps.append(timestamp)
            rows.append(values)
    elif dataset.kind == "weather_tsv":
        columns = ["wind_speed", "wind_direction", "air_temperature", "atmosphere", "relative_humidity"]
        for record in packet.records:
            cells = split_delimited(record.text, "\t")
            if not cells or "日期" in cells[0] or cells[0].lower().startswith("date"):
                continue
            timestamp = parse_datetime_ms(cells[0])
            if timestamp is None:
                continue
            values = [parse_float(cells[index]) if index < len(cells) else math.nan for index in range(1, 6)]
            timestamps.append(timestamp)
            rows.append(values)
    elif dataset.kind == "wave_sensor_tsv":
        columns = [
            "ax",
            "ay",
            "az",
            "wx",
            "wy",
            "wz",
            "angle_x",
            "angle_y",
            "angle_z",
            "temperature",
            "hx",
            "hy",
            "hz",
        ]
        for record in packet.records:
            text = clean_cell(record.text)
            if not text or text.startswith("StartTime") or text.startswith("address"):
                continue
            cells = split_delimited(record.text, "\t")
            if len(cells) < 3:
                continue
            timestamp = parse_datetime_ms(cells[2])
            if timestamp is None:
                continue
            values = [parse_float(cells[index]) if index < len(cells) else math.nan for index in range(3, 16)]
            timestamps.append(timestamp)
            rows.append(values)
    elif dataset.kind == "ocean_current_log":
        raw_rows = []
        max_width = 0
        for record in packet.records:
            text = record.text
            match = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", text)
            if not match:
                continue
            timestamp = parse_datetime_ms(match.group(1))
            if timestamp is None:
                continue
            if "adcp_preprocessing_data" not in text:
                continue
            payload = text.split("adcp_preprocessing_data", 1)[-1]
            numbers = [float(item) for item in re.findall(r"[-+]?\d+(?:\.\d+)?", payload)]
            if not numbers:
                continue
            max_width = max(max_width, len(numbers))
            timestamps.append(timestamp)
            raw_rows.append(numbers)
        columns = [f"num_{index:03d}" for index in range(max_width)]
        for row in raw_rows:
            rows.append(row + [math.nan] * (max_width - len(row)))
    else:
        columns = []

    values = {column: [] for column in columns}
    for row in rows:
        for index, column in enumerate(columns):
            values[column].append(row[index] if index < len(row) else math.nan)
    return NumericPacket(timestamps=timestamps, columns=columns, values=values)


def parse_level(text):
    match = re.search(r"\s(INFO|WARN|ERROR|DEBUG|TRACE)\s+", text)
    return match.group(1) if match else ""


def table_rows_from_records(dataset, packet):
    rows = []
    if dataset.kind == "big_weather_csv":
        columns = [
            "time",
            "air_temperature",
            "atmosphere",
            "wind_speed",
            "wind_direction",
            "maximum_instantaneous_air_speed",
            "wind_direction_at_maximum_instantaneous_wind_speed",
            "relative_humidity",
            "rainfall",
            "heading",
            "pitch",
            "roll",
        ]
        for record in packet.records:
            cells = split_delimited(record.text, ",")
            if not cells or clean_cell(cells[0]).lower() == "time":
                continue
            timestamp = clean_cell(cells[0])
            if parse_datetime_ms(timestamp) is None:
                continue
            row = {"time": timestamp}
            for index, column in enumerate(columns[1:], start=1):
                row[column] = None if index >= len(cells) or clean_cell(cells[index]) == "" else parse_float(cells[index])
            rows.append(row)
    elif dataset.kind == "weather_tsv":
        columns = ["time", "wind_speed", "wind_direction", "air_temperature", "atmosphere", "relative_humidity"]
        for record in packet.records:
            cells = split_delimited(record.text, "\t")
            if not cells or "日期" in cells[0]:
                continue
            timestamp = clean_cell(cells[0])
            if parse_datetime_ms(timestamp) is None:
                continue
            row = {"time": timestamp}
            for index, column in enumerate(columns[1:], start=1):
                row[column] = None if index >= len(cells) or clean_cell(cells[index]) == "" else parse_float(cells[index])
            rows.append(row)
    elif dataset.kind == "wave_sensor_tsv":
        columns = [
            "address",
            "time_s",
            "chip_time",
            "ax",
            "ay",
            "az",
            "wx",
            "wy",
            "wz",
            "angle_x",
            "angle_y",
            "angle_z",
            "temperature",
            "hx",
            "hy",
            "hz",
        ]
        for record in packet.records:
            text = clean_cell(record.text)
            if not text or text.startswith("StartTime") or text.startswith("address"):
                continue
            cells = split_delimited(record.text, "\t")
            if len(cells) < 3 or parse_datetime_ms(cells[2]) is None:
                continue
            row = {"address": cells[0], "time_s": cells[1], "chip_time": cells[2]}
            for index, column in enumerate(columns[3:], start=3):
                row[column] = None if index >= len(cells) or clean_cell(cells[index]) == "" else parse_float(cells[index])
            rows.append(row)
    elif dataset.kind == "ocean_current_log":
        for record in packet.records:
            text = record.text.strip()
            match = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", text)
            if not match:
                continue
            event_type = "other"
            if "adcp_raw_data" in text:
                event_type = "adcp_raw_data"
            elif "adcp_preprocessing_data" in text:
                event_type = "adcp_preprocessing_data"
            rows.append(
                {
                    "timestamp": match.group(1),
                    "source_file": record.source_file,
                    "line_no": record.line_no,
                    "level": parse_level(text),
                    "event_type": event_type,
                    "message": text,
                    "message_bytes": len(record.raw),
                }
            )
    return rows


def values_equal(left, right):
    if len(left.timestamps) != len(right.timestamps) or left.columns != right.columns:
        return False
    if left.timestamps != right.timestamps:
        return False
    for column in left.columns:
        left_values = left.values[column]
        right_values = right.values[column]
        if len(left_values) != len(right_values):
            return False
        for a, b in zip(left_values, right_values):
            if float_to_bits(a) != float_to_bits(b):
                return False
    return True


def gzip_compress(data):
    try:
        return gzip.compress(data, compresslevel=6, mtime=0)
    except TypeError:
        return gzip.compress(data, compresslevel=6)


def run_gzip(dataset, packet):
    expected = packet.raw
    compressed = gzip_compress(expected)
    restored = gzip.decompress(compressed)
    return compressed, restored == expected, "byte_exact", len(expected)


def run_numeric_codec(dataset, packet, codec):
    expected = numeric_packet_from_records(dataset, packet)
    compressed = encode_numeric_packet(expected, codec)
    restored = decode_numeric_packet(compressed)
    return compressed, values_equal(expected, restored), "logical_numeric", len(packet.raw)


def build_native_numeric_packets(dataset, packets):
    return [numeric_packet_from_records(dataset, packet) for packet in packets]


def write_native_numeric_batch(path, numeric_packets):
    with path.open("wb") as stream:
        stream.write(b"OCNBATCH1")
        stream.write(pack_u32(len(numeric_packets)))
        for numeric in numeric_packets:
            row_count = len(numeric.timestamps)
            stream.write(pack_u32(row_count))
            stream.write(pack_u32(len(numeric.columns)))
            for timestamp in numeric.timestamps:
                stream.write(struct.pack(">q", int(timestamp)))
            for column in numeric.columns:
                for value in numeric.values[column]:
                    stream.write(struct.pack(">Q", float_to_bits(value)))


def run_native_numeric_group(dataset, packets, codec, native_codec_bin):
    native_codec_bin = Path(native_codec_bin)
    if not native_codec_bin.exists():
        raise FileNotFoundError(f"Native numeric codec not found: {native_codec_bin}")

    original_size = sum(len(packet.raw) for packet in packets)
    preprocess_start = time.perf_counter()
    numeric_packets = build_native_numeric_packets(dataset, packets)
    preprocess_time = time.perf_counter() - preprocess_start
    with tempfile.TemporaryDirectory(prefix="ocean_numeric_codec_") as temp_dir:
        batch_path = Path(temp_dir) / "numeric_batch.bin"
        write_native_numeric_batch(batch_path, numeric_packets)
        completed = subprocess.run(
            [str(native_codec_bin), "--codec", codec, "--input", str(batch_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    metrics = json.loads(completed.stdout)
    compression_time = preprocess_time + float(metrics["compression_time_ms"]) / 1000.0
    decompression_time = float(metrics["decompression_time_ms"]) / 1000.0
    compressed_size = int(metrics["compressed_size_bytes"])
    original_mb = original_size / (1024 * 1024)
    return {
        "status": "ok",
        "skip_reason": "",
        "compressed_size_bytes": compressed_size,
        "original_size_bytes": original_size,
        "compression_time_ms": compression_time * 1000.0,
        "decompression_time_ms": decompression_time * 1000.0,
        "compression_ratio": compressed_size / original_size if original_size else "",
        "compression_throughput_MBps": original_mb / compression_time if compression_time else "",
        "decompression_throughput_MBps": original_mb / decompression_time if decompression_time else "",
        "integrity": metrics.get("integrity", "fail"),
        "integrity_scope": "parsed_ts_logical_numeric_native",
        "valid_packets": int(metrics.get("valid_packets", len(packets))),
    }


def algorithm_input_object(algorithm):
    if algorithm == "gzip":
        return "raw_bytes"
    if algorithm in {"gorilla", "chimp"}:
        return "parsed_time_series"
    if algorithm.startswith("parquet_"):
        return "typed_table"
    return ""


def algorithm_preprocessing_scope(algorithm):
    if algorithm == "gzip":
        return "none_raw_packet_bytes"
    if algorithm in {"gorilla", "chimp"}:
        return "parse_timestamp_and_numeric_columns"
    if algorithm.startswith("parquet_"):
        return "parse_records_and_build_typed_table"
    return ""


def parquet_available():
    try:
        import pyarrow  # noqa: F401
        import pyarrow.parquet  # noqa: F401
        return True, ""
    except Exception as exc:
        return False, str(exc)


def run_parquet(dataset, packet, compression):
    import pyarrow as pa
    import pyarrow.parquet as pq

    expected = table_rows_from_records(dataset, packet)
    table = pa.Table.from_pylist(expected if expected else [{"__empty_packet": True}])
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression=compression)
    compressed = buffer.getvalue()
    restored_table = pq.read_table(io.BytesIO(compressed))
    restored = restored_table.to_pylist()
    if not expected:
        restored_ok = restored == [{"__empty_packet": True}]
    else:
        restored_ok = restored == expected
    return compressed, restored_ok, "logical_table", len(packet.raw)


def benchmark_group(dataset, packets, algorithm, numeric_codec_backend="auto", native_codec_bin=NATIVE_CODEC_BIN):
    compressed_size = 0
    original_size = 0
    compression_time = 0.0
    decompression_time = 0.0
    integrity_ok = True
    integrity_scope = ""
    valid_packets = 0

    available = True
    reason = ""
    if algorithm.startswith("parquet_"):
        available, reason = parquet_available()
    if not available:
        return {
            "status": "skipped",
            "skip_reason": reason,
            "compressed_size_bytes": "",
            "original_size_bytes": sum(len(packet.raw) for packet in packets),
            "compression_time_ms": "",
            "decompression_time_ms": "",
            "compression_ratio": "",
            "compression_throughput_MBps": "",
            "decompression_throughput_MBps": "",
            "integrity": "skipped",
            "integrity_scope": "",
            "valid_packets": "",
        }

    if algorithm in {"gorilla", "chimp"} and numeric_codec_backend != "python":
        native_path = Path(native_codec_bin)
        if native_path.exists():
            return run_native_numeric_group(dataset, packets, algorithm, native_path)
        if numeric_codec_backend == "native":
            raise FileNotFoundError(f"Native numeric codec not found: {native_path}")

    for packet in packets:
        original_size += len(packet.raw)
        start = time.perf_counter()
        if algorithm == "gzip":
            expected = packet.raw
            compressed = gzip_compress(expected)
            after_compress = time.perf_counter()
            restored = gzip.decompress(compressed)
            ok = restored == expected
            scope = "byte_exact"
        elif algorithm == "gorilla":
            expected = numeric_packet_from_records(dataset, packet)
            compressed = encode_numeric_packet(expected, "gorilla")
            after_compress = time.perf_counter()
            restored = decode_numeric_packet(compressed)
            ok = values_equal(expected, restored)
            scope = "logical_numeric"
        elif algorithm == "chimp":
            expected = numeric_packet_from_records(dataset, packet)
            compressed = encode_numeric_packet(expected, "chimp")
            after_compress = time.perf_counter()
            restored = decode_numeric_packet(compressed)
            ok = values_equal(expected, restored)
            scope = "logical_numeric"
        elif algorithm == "parquet_zstd":
            import pyarrow as pa
            import pyarrow.parquet as pq

            expected = table_rows_from_records(dataset, packet)
            table = pa.Table.from_pylist(expected if expected else [{"__empty_packet": True}])
            buffer = io.BytesIO()
            pq.write_table(table, buffer, compression="zstd")
            compressed = buffer.getvalue()
            after_compress = time.perf_counter()
            restored = pq.read_table(io.BytesIO(compressed)).to_pylist()
            ok = restored == (expected if expected else [{"__empty_packet": True}])
            scope = "logical_table"
        elif algorithm == "parquet_snappy":
            import pyarrow as pa
            import pyarrow.parquet as pq

            expected = table_rows_from_records(dataset, packet)
            table = pa.Table.from_pylist(expected if expected else [{"__empty_packet": True}])
            buffer = io.BytesIO()
            pq.write_table(table, buffer, compression="snappy")
            compressed = buffer.getvalue()
            after_compress = time.perf_counter()
            restored = pq.read_table(io.BytesIO(compressed)).to_pylist()
            ok = restored == (expected if expected else [{"__empty_packet": True}])
            scope = "logical_table"
        else:
            raise ValueError(f"unsupported algorithm: {algorithm}")
        after_decompress = time.perf_counter()
        compressed_size += len(compressed)
        compression_time += after_compress - start
        decompression_time += after_decompress - after_compress
        integrity_ok = integrity_ok and ok
        integrity_scope = integrity_scope or scope
        valid_packets += 1

    original_mb = original_size / (1024 * 1024)
    return {
        "status": "ok",
        "skip_reason": "",
        "compressed_size_bytes": compressed_size,
        "original_size_bytes": original_size,
        "compression_time_ms": compression_time * 1000.0,
        "decompression_time_ms": decompression_time * 1000.0,
        "compression_ratio": compressed_size / original_size if original_size else "",
        "compression_throughput_MBps": original_mb / compression_time if compression_time else "",
        "decompression_throughput_MBps": original_mb / decompression_time if decompression_time else "",
        "integrity": "pass" if integrity_ok else "fail",
        "integrity_scope": integrity_scope,
        "valid_packets": valid_packets,
    }


def packet_summary(dataset, packet_size, packets):
    sizes = [len(packet.raw) for packet in packets]
    long_records = sum(1 for record in dataset.records if len(record.raw) > packet_size)
    return {
        "dataset": dataset.dataset_id,
        "source_files": ";".join(dataset.source_files),
        "encoding": dataset.encoding,
        "kind": dataset.kind,
        "original_size_bytes": dataset.raw_size_bytes,
        "original_size_MB": dataset.raw_size_bytes / (1024 * 1024),
        "record_count": len(dataset.records),
        "packet_size": packet_size,
        "packet_count": len(packets),
        "avg_packet_bytes": sum(sizes) / len(sizes) if sizes else 0,
        "min_packet_bytes": min(sizes) if sizes else 0,
        "max_packet_bytes": max(sizes) if sizes else 0,
        "total_packet_bytes": sum(sizes),
        "long_record_count": long_records,
    }


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path, row, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def read_existing_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def format_value(value):
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.9f}"
    return value


def normalized_rows(rows):
    return [{key: format_value(value) for key, value in row.items()} for row in rows]


def build_end_to_end_rows(measurement_rows, bandwidths_mbps):
    rows = []
    for row in measurement_rows:
        if row["status"] != "ok" or row["integrity"] != "pass":
            continue
        original_size = int(row["original_size_bytes"])
        compressed_size = int(row["compressed_size_bytes"])
        compression_ms = float(row["compression_time_ms"])
        decompression_ms = float(row["decompression_time_ms"])
        for bandwidth in bandwidths_mbps:
            bandwidth_bps = bandwidth * 1_000_000.0
            transfer_ms = compressed_size * 8.0 / bandwidth_bps * 1000.0
            direct_ms = original_size * 8.0 / bandwidth_bps * 1000.0
            total_ms = compression_ms + transfer_ms + decompression_ms
            reduction = (direct_ms - total_ms) / direct_ms * 100.0 if direct_ms else 0.0
            output = dict(row)
            output.update(
                {
                    "bandwidth_mbps": bandwidth,
                    "T_transfer_ms": transfer_ms,
                    "T_direct_ms": direct_ms,
                    "T_total_ms": total_ms,
                    "latency_reduction_pct": reduction,
                }
            )
            rows.append(output)
    return rows


def build_best_rows(end_to_end_rows):
    groups = {}
    for row in end_to_end_rows:
        key = (
            str(row["dataset"]),
            str(row["packet_size"]),
            f"{float(row['bandwidth_mbps']):.9f}",
            str(row["cpu_limit"]),
            str(row["repeat"]),
        )
        groups.setdefault(key, []).append(row)
    best_rows = []
    for key, rows in sorted(groups.items()):
        best = min(rows, key=lambda row: float(row["T_total_ms"]))
        best_rows.append(
            {
                "dataset": key[0],
                "packet_size": key[1],
                "bandwidth_mbps": key[2],
                "cpu_limit": key[3],
                "repeat": key[4],
                "best_algorithm": best["algorithm"],
                "best_T_total_ms": best["T_total_ms"],
                "best_latency_reduction_pct": best["latency_reduction_pct"],
                "best_compression_ratio": best["compression_ratio"],
            }
        )
    return best_rows


def main():
    parser = argparse.ArgumentParser(description="Run ocean per-packet compression experiments.")
    parser.add_argument(
        "--input-dir",
        default=str(OCEAN_DATA),
        help="Directory containing the extracted ocean observation data files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OCEAN_ROOT / "runs" / "文本压缩" / "compression_experiment"),
        help="Directory for CSV outputs.",
    )
    parser.add_argument("--datasets", default="", help="Comma-separated dataset ids to run. Empty means all discovered.")
    parser.add_argument("--algorithms", default=",".join(ALGORITHMS), help="Comma-separated algorithms.")
    parser.add_argument("--packet-sizes", default="512,1448,4096", help="Comma-separated packet sizes in bytes.")
    parser.add_argument("--bandwidths-mbps", default="2,4,10", help="Comma-separated bandwidths in Mbps.")
    parser.add_argument("--cpu-limit-label", default="100", help="Label for externally enforced CPU limit.")
    parser.add_argument("--repeats", type=int, default=5, help="Repeated measurements per group.")
    parser.add_argument("--max-packets", type=int, default=0, help="Limit packets per dataset for smoke tests. 0 means all.")
    parser.add_argument("--summary-only", action="store_true", help="Only build packet summary; skip compression.")
    parser.add_argument("--resume", action="store_true", help="Skip groups already present in compression_measurements.csv.")
    parser.add_argument("--incremental", action="store_true", help="Append each completed group to compression_measurements.csv immediately.")
    parser.add_argument(
        "--numeric-codec-backend",
        choices=["auto", "python", "native"],
        default="auto",
        help="Backend for Gorilla/Chimp numeric codecs. auto uses native binary when present.",
    )
    parser.add_argument(
        "--native-codec-bin",
        default=str(NATIVE_CODEC_BIN),
        help="Path to native Gorilla/Chimp numeric codec executable.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    algorithms = parse_list(args.algorithms, str)
    packet_sizes = parse_list(args.packet_sizes, int)
    bandwidths = parse_list(args.bandwidths_mbps, float)
    selected_datasets = set(parse_list(args.datasets, str)) if args.datasets else None

    unknown = [algorithm for algorithm in algorithms if algorithm not in ALGORITHMS]
    if unknown:
        raise ValueError(f"Unknown algorithms: {unknown}. Supported: {ALGORITHMS}")
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    datasets = discover_datasets(input_dir)
    if selected_datasets:
        datasets = [dataset for dataset in datasets if dataset.dataset_id in selected_datasets]
    if not datasets:
        raise RuntimeError(f"No datasets found in {input_dir}")

    measurement_fields = [
        "dataset",
        "source_files",
        "kind",
        "algorithm",
        "input_object",
        "preprocessing_scope",
        "packet_size",
        "cpu_limit",
        "repeat",
        "packet_count",
        "status",
        "skip_reason",
        "original_size_bytes",
        "compressed_size_bytes",
        "compression_ratio",
        "compression_time_ms",
        "decompression_time_ms",
        "compression_throughput_MBps",
        "decompression_throughput_MBps",
        "integrity",
        "integrity_scope",
        "valid_packets",
    ]
    measurement_path = output_dir / "compression_measurements.csv"
    existing_rows = read_existing_csv(measurement_path) if args.resume else []
    completed = {
        (
            row.get("dataset", ""),
            row.get("algorithm", ""),
            str(row.get("packet_size", "")),
            str(row.get("cpu_limit", "")),
            str(row.get("repeat", "")),
        )
        for row in existing_rows
    }
    if args.resume and existing_rows:
        print(f"Resume enabled: loaded {len(existing_rows)} existing measurement rows")

    packet_summary_rows = []
    measurement_rows = list(existing_rows)

    for dataset in datasets:
        print(f"Dataset {dataset.dataset_id}: {len(dataset.records)} records, {dataset.raw_size_bytes} bytes")
        for packet_size in packet_sizes:
            packets = build_packets(dataset.records, packet_size)
            if args.max_packets > 0:
                packets = packets[: args.max_packets]
            summary = packet_summary(dataset, packet_size, packets)
            packet_summary_rows.append(summary)
            print(f"  packet_size={packet_size}: {len(packets)} packets")
            if args.summary_only:
                continue
            for algorithm in algorithms:
                for repeat in range(1, args.repeats + 1):
                    key = (dataset.dataset_id, algorithm, str(packet_size), str(args.cpu_limit_label), str(repeat))
                    if key in completed:
                        print(f"    {algorithm} repeat {repeat}/{args.repeats} skipped (resume)")
                        continue
                    print(f"    {algorithm} repeat {repeat}/{args.repeats}")
                    try:
                        result = benchmark_group(
                            dataset,
                            packets,
                            algorithm,
                            numeric_codec_backend=args.numeric_codec_backend,
                            native_codec_bin=args.native_codec_bin,
                        )
                    except Exception as exc:
                        result = {
                            "status": "error",
                            "skip_reason": repr(exc),
                            "compressed_size_bytes": "",
                            "original_size_bytes": sum(len(packet.raw) for packet in packets),
                            "compression_time_ms": "",
                            "decompression_time_ms": "",
                            "compression_ratio": "",
                            "compression_throughput_MBps": "",
                        "decompression_throughput_MBps": "",
                        "integrity": "fail",
                        "integrity_scope": "",
                        "valid_packets": "",
                    }
                    row = {
                        "dataset": dataset.dataset_id,
                        "source_files": ";".join(dataset.source_files),
                        "kind": dataset.kind,
                        "algorithm": algorithm,
                        "input_object": algorithm_input_object(algorithm),
                        "preprocessing_scope": algorithm_preprocessing_scope(algorithm),
                        "packet_size": packet_size,
                        "cpu_limit": args.cpu_limit_label,
                        "repeat": repeat,
                        "packet_count": len(packets),
                    }
                    row.update(result)
                    measurement_rows.append(row)
                    completed.add(key)
                    if args.incremental:
                        append_csv(measurement_path, normalized_rows([row])[0], measurement_fields)

    packet_summary_fields = [
        "dataset",
        "source_files",
        "encoding",
        "kind",
        "original_size_bytes",
        "original_size_MB",
        "record_count",
        "packet_size",
        "packet_count",
        "avg_packet_bytes",
        "min_packet_bytes",
        "max_packet_bytes",
        "total_packet_bytes",
        "long_record_count",
    ]
    write_csv(output_dir / "packet_summary.csv", normalized_rows(packet_summary_rows), packet_summary_fields)

    if measurement_rows:
        write_csv(output_dir / "compression_measurements.csv", normalized_rows(measurement_rows), measurement_fields)
        end_to_end_rows = build_end_to_end_rows(measurement_rows, bandwidths)
        end_to_end_fields = measurement_fields + [
            "bandwidth_mbps",
            "T_transfer_ms",
            "T_direct_ms",
            "T_total_ms",
            "latency_reduction_pct",
        ]
        write_csv(output_dir / "end_to_end_results.csv", normalized_rows(end_to_end_rows), end_to_end_fields)
        best_rows = build_best_rows(end_to_end_rows)
        best_fields = [
            "dataset",
            "packet_size",
            "bandwidth_mbps",
            "cpu_limit",
            "repeat",
            "best_algorithm",
            "best_T_total_ms",
            "best_latency_reduction_pct",
            "best_compression_ratio",
        ]
        write_csv(output_dir / "best_algorithm_by_scenario.csv", normalized_rows(best_rows), best_fields)

    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
