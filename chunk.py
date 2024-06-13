from abc import abstractmethod
from enum import Enum
from typing import Literal, Type


class ChunkType(Enum):
    UNKNOWN = -1
    RIFF = 0
    STANDARD_FMT = 1
    NON_STANDARD_FMT = 2
    EXTENSIBLE_FMT = 3
    DATA = 4
    BEXT = 6


class BaseChunk(object):

    def __init__(self):
        self.chunk_name = ""
        self.chunk_type = ChunkType.UNKNOWN
        self.chunk_size = 0
        self.valid = False

    @abstractmethod
    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):
        self.chunk_name = self.get_chunk_name(byte_seq, chunk_start_pos)
        self.chunk_type = self.get_chunk_type(byte_seq, chunk_start_pos)
        self.chunk_size = self.get_chunk_size(byte_seq, chunk_start_pos)

    @classmethod
    def get_chunk_type(cls, byte_seq: bytes, chunk_start_pos: int = 0) -> ChunkType:
        if chunk_start_pos + 4 > len(byte_seq):
            return ChunkType.UNKNOWN

        chunk_name = cls.get_chunk_name(byte_seq, chunk_start_pos)
        if chunk_name == "RIFF":
            return ChunkType.RIFF
        elif chunk_name == "fmt ":
            chunk_size = cls.get_chunk_size(byte_seq, chunk_start_pos)
            if chunk_size == 16:
                return ChunkType.STANDARD_FMT
            elif chunk_size == 18:
                return ChunkType.NON_STANDARD_FMT
            elif chunk_size == 40:
                return ChunkType.EXTENSIBLE_FMT
            else:
                return ChunkType.UNKNOWN
        elif chunk_name == "data":
            return ChunkType.DATA
        elif chunk_name == "bext":
            return ChunkType.BEXT

    @staticmethod
    def get_chunk_name(byte_seq: bytes, chunk_start_pos: int = 0) -> str:
        if chunk_start_pos + 4 > len(byte_seq):
            return ""

        return byte_seq[chunk_start_pos:chunk_start_pos + 4].decode("utf-8")

    @staticmethod
    def get_chunk_size(byte_seq: bytes, chunk_start_pos: int = 0) -> int:
        if chunk_start_pos + 8 > len(byte_seq):
            return -1

        return BaseChunk.parse_int(byte_seq, chunk_start_pos + 4, chunk_start_pos + 8)

    @staticmethod
    def parse_int(
        byte_seq: bytes,
        start_pos: int = 0,
        length: int = 4,
        byte_order: Literal["little", "big"] = "little",
        signed: bool = False,
    ) -> int:
        return int.from_bytes(byte_seq[start_pos:length], byteorder=byte_order, signed=signed)

    @staticmethod
    def parse_str(byte_seq: bytes, start_pos: int = 0, end_pos: int = -1) -> str:
        if end_pos == -1:
            end_pos = len(byte_seq)

        end_flag_idx = byte_seq.find(b"\0", start_pos, end_pos)
        if end_flag_idx == -1:
            end_flag_idx = end_pos

        if start_pos >= end_flag_idx:
            return ""

        try:
            return byte_seq[start_pos:end_flag_idx].decode("utf-8")
        except UnicodeDecodeError:
            return ""

    def get_bytes(
        self,
        byte_data: bytes,
        start_pos: int,
        length: int,
        valid_check: bool = True,
    ) -> (bytes, int):
        if start_pos + length > len(byte_data):
            self.valid = (not valid_check) and self.valid
            return b"", start_pos + length

        return byte_data[start_pos:start_pos + length], start_pos + length


class RiffChunk(BaseChunk):

    def __init__(self):
        super().__init__()
        self.wave_symbol: str = ""

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check name, type and size
        if self.chunk_name != "RIFF":
            self.valid = False
        if self.chunk_type != ChunkType.RIFF:
            self.valid = False
        if self.chunk_size != 4:
            self.valid = False

        # check wave symbol
        wave_symbol_bytes, _ = self.get_bytes(byte_seq, chunk_start_pos + 8, 4)
        self.wave_symbol = self.parse_str(wave_symbol_bytes)
        if self.wave_symbol != "WAVE":
            self.valid = False


class BaseFormatChunk(BaseChunk):

    class FormatTag(Enum):
        UNKNOWN = -1
        PCM = 1
        IEEE_FLOAT = 3
        ALAW = 6
        MULAW = 7
        EXTENSIBLE = 0xFFFE

    def __init__(self):
        super().__init__()
        self.format_tag: BaseFormatChunk.FormatTag = BaseFormatChunk.FormatTag.UNKNOWN
        self._channels: bytes = b""
        self._sample_rate: bytes = b""
        self._byte_rate: bytes = b""
        self._block_align: bytes = b""
        self._bits_per_sample: bytes = b""

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check name
        if self.chunk_name != "fmt ":
            self.valid = False

        start_pos = chunk_start_pos + 8

        # check format tag
        format_tag_bytes, start_pos = self.get_bytes(byte_seq, start_pos, length=2)
        self.format_tag = self._get_format_tag(format_tag_bytes)

        # check channels
        self._channels, start_pos = self.get_bytes(byte_seq, start_pos, length=2)

        # check sample rate
        self._sample_rate, start_pos = self.get_bytes(byte_seq, start_pos, length=4)

        # check byte rate
        self._byte_rate, start_pos = self.get_bytes(byte_seq, start_pos, length=4)

        # check block align
        self._block_align, start_pos = self.get_bytes(byte_seq, start_pos, length=2)

        # check bits per sample
        self._bits_per_sample, start_pos = self.get_bytes(byte_seq, start_pos, length=2)

    def _get_format_tag(self, byte_data: bytes) -> "BaseFormatChunk.FormatTag":
        format_tag_int = self.parse_int(byte_data, 0, 2)
        if format_tag_int == 1:
            return BaseFormatChunk.FormatTag.PCM
        elif format_tag_int == 3:
            return BaseFormatChunk.FormatTag.IEEE_FLOAT
        elif format_tag_int == 6:
            return BaseFormatChunk.FormatTag.ALAW
        elif format_tag_int == 7:
            return BaseFormatChunk.FormatTag.MULAW
        elif format_tag_int == 0xFFFE:
            return BaseFormatChunk.FormatTag.EXTENSIBLE
        else:
            return BaseFormatChunk.FormatTag.UNKNOWN

    @property
    def channels(self) -> int:
        return self.parse_int(self._channels, length=2)

    @property
    def sample_rate(self) -> int:
        return self.parse_int(self._sample_rate, length=4)

    @property
    def byte_rate(self) -> int:
        return self.parse_int(self._byte_rate, length=4)

    @property
    def block_align(self) -> int:
        return self.parse_int(self._block_align, length=2)

    @property
    def bits_per_sample(self) -> int:
        return self.parse_int(self._bits_per_sample, length=2)


class StandardPCMFormatChunk(BaseFormatChunk):

    def __init__(self):
        super().__init__()

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check type and size
        if self.chunk_type != ChunkType.STANDARD_FMT:
            self.valid = False
        if self.chunk_size != 16:
            self.valid = False


class NonPCMFormatChunk(BaseFormatChunk):

    def __init__(self):
        super().__init__()

        self._extension_size: bytes = b""

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check type and size
        if self.chunk_type != ChunkType.NON_STANDARD_FMT:
            self.valid = False
        if self.chunk_size != 18:
            self.valid = False

        # check extension chunk size
        self._extension_size, _ = self.get_bytes(byte_seq, chunk_start_pos + 24, 2)

    @property
    def extension_size(self) -> int:
        return self.parse_int(self._extension_size, 0, 2)


class ExtensibleFormatChunk(BaseFormatChunk):

    def __init__(self):
        super().__init__()

        self._extension_size: bytes = b""
        self._valid_bits_per_sample: bytes = b""
        self._channel_mask: bytes = b""
        self.sub_format: bytes = b""

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check type and size
        if self.chunk_type != ChunkType.EXTENSIBLE_FMT:
            self.valid = False
        if self.chunk_size != 40:
            self.valid = False

        start_pos = chunk_start_pos + 24

        # check extension size
        self._extension_size, start_pos = self.get_bytes(byte_seq, start_pos, length=2)

        # check valid bits per sample
        self._valid_bits_per_sample, start_pos = self.get_bytes(byte_seq, start_pos, length=2)

        # check channel mask
        self._channel_mask, start_pos = self.get_bytes(byte_seq, start_pos, length=4)

        # check sub format
        self.sub_format, start_pos = self.get_bytes(byte_seq, start_pos, length=16)

    @property
    def extension_size(self) -> int:
        return self.parse_int(self._extension_size, length=2)

    @property
    def valid_bits_per_sample(self) -> int:
        return self.parse_int(self._valid_bits_per_sample, length=2)

    @property
    def channel_mask(self) -> int:
        return self.parse_int(self._channel_mask, length=4)


class DataChunk(BaseChunk):

    def __init__(self):
        super().__init__()
        self.data: bytes = b""

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check name, type
        if self.chunk_name != "data":
            self.valid = False
        if self.chunk_type != ChunkType.DATA:
            self.valid = False

        # check data
        self.data, _ = self.get_bytes(byte_seq, chunk_start_pos + 8, self.chunk_size)


class FactChunk(BaseChunk):

    def __init__(self):
        super().__init__()
        self._sample_length: bytes = b""

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check name, type and size
        if self.chunk_name != "fact":
            self.valid = False
        if self.chunk_type != ChunkType.UNKNOWN:
            self.valid = False
        if self.chunk_size != 4:
            self.valid = False

        # check sample length
        self._sample_length, _ = self.get_bytes(byte_seq, chunk_start_pos + 8, 4)

    @property
    def sample_length(self) -> int:
        return self.parse_int(self._sample_length, length=4)


class BextChunk(BaseChunk):

    def __init__(self):
        super().__init__()
        self._description: bytes = b""
        self._originator: bytes = b""
        self._originator_reference: bytes = b""
        self._originator_date: bytes = b""
        self._originator_time: bytes = b""
        self._align: bytes = b""
        self._time_reference_low: bytes = b""
        self._time_reference_high: bytes = b""
        self._version: bytes = b""
        self.umid: bytes = b""
        self._loudness_value: bytes = b""
        self._loudness_range: bytes = b""
        self._max_true_peak_level: bytes = b""
        self._max_momentary_loudness: bytes = b""
        self._max_short_term_loudness: bytes = b""
        self.reserved: bytes = b""

    def parse(self, byte_seq: bytes, chunk_start_pos: int = 0):

        super().parse(byte_seq, chunk_start_pos)

        # check name, type
        if self.chunk_name != "bext":
            self.valid = False
        if self.chunk_type != ChunkType.BEXT:
            self.valid = False

        start_pos = chunk_start_pos + 8

        # check description
        self._description, start_pos = self.get_bytes(byte_seq, start_pos, 256)

        # check originator
        self._originator, start_pos = self.get_bytes(byte_seq, start_pos, 32)

        # check originator reference
        self._originator_reference, start_pos = self.get_bytes(byte_seq, start_pos, 32)

        # check originator date
        self._originator_date, start_pos = self.get_bytes(byte_seq, start_pos, 10)

        # check originator time
        self._originator_time, start_pos = self.get_bytes(byte_seq, start_pos, 8)

        # check align
        self._align, start_pos = self.get_bytes(byte_seq, start_pos, 2)

        # check time reference low
        self._time_reference_low, start_pos = self.get_bytes(byte_seq, start_pos, 4)

        # check time reference high
        self._time_reference_high, start_pos = self.get_bytes(byte_seq, start_pos, 4)

        # check version
        self._version, start_pos = self.get_bytes(byte_seq, start_pos, 1, valid_check=False)

        # check umid
        self.umid, start_pos = self.get_bytes(byte_seq, start_pos, 64, valid_check=False)

        # check loudness value
        self._loudness_value, start_pos = self.get_bytes(byte_seq, start_pos, 2, valid_check=False)

        # check loudness range
        self._loudness_range, start_pos = self.get_bytes(byte_seq, start_pos, 2, valid_check=False)

        # check max true peak level
        self._max_true_peak_level, start_pos = self.get_bytes(byte_seq, start_pos, 2, valid_check=False)

        # check max momentary loudness
        self._max_momentary_loudness, start_pos = self.get_bytes(byte_seq, start_pos, 2, valid_check=False)

        # check max short term loudness
        self._max_short_term_loudness, start_pos = self.get_bytes(byte_seq, start_pos, 2, valid_check=False)

        # check reserved
        self.reserved, start_pos = self.get_bytes(byte_seq, start_pos, 180, valid_check=False)

    @property
    def description(self) -> str:
        return self.parse_str(self._description)

    @property
    def originator(self) -> str:
        return self.parse_str(self._originator)

    @property
    def originator_reference(self) -> str:
        return self.parse_str(self._originator_reference)

    @property
    def originator_date(self) -> str:
        return self.parse_str(self._originator_date)

    @property
    def originator_time(self) -> str:
        return self.parse_str(self._originator_time)

    @property
    def align(self) -> int:
        return self.parse_int(self._align, length=2)

    @property
    def time_reference_low(self) -> int:
        return self.parse_int(self._time_reference_low, length=4)

    @property
    def time_reference_high(self) -> int:
        return self.parse_int(self._time_reference_high, length=4)

    @property
    def version(self) -> int:
        return self.parse_int(self._version, length=1)

    @property
    def loudness_value(self) -> int:
        return self.parse_int(self._loudness_value, length=2)

    @property
    def loudness_range(self) -> int:
        return self.parse_int(self._loudness_range, length=2)

    @property
    def max_true_peak_level(self) -> int:
        return self.parse_int(self._max_true_peak_level, length=2)

    @property
    def max_momentary_loudness(self) -> int:
        return self.parse_int(self._max_momentary_loudness, length=2)

    @property
    def max_short_term_loudness(self) -> int:
        return self.parse_int(self._max_short_term_loudness, length=2)


CHUNK_TYPE_MAP: dict[ChunkType, Type[BaseChunk]] = {
    ChunkType.UNKNOWN: BaseChunk,
    ChunkType.RIFF: RiffChunk,
    ChunkType.STANDARD_FMT: StandardPCMFormatChunk,
    ChunkType.NON_STANDARD_FMT: NonPCMFormatChunk,
    ChunkType.EXTENSIBLE_FMT: ExtensibleFormatChunk,
    ChunkType.DATA: DataChunk,
    ChunkType.BEXT: BextChunk,
}
