#!/usr/bin/python3.11

"""
base.py
"""

import hashlib
# Imports
from abc import ABC, abstractmethod
from typing import BinaryIO, NamedTuple, Any, Type, Literal, cast

__all__ = ["STFBaseException", "STFCriticalException", "STFNonCriticalException", "STFUnboundStringException", "STFOverRead", "STFMagicNumberException", "STFVersionException", "Configuration", "Utility", "STFObject", "STFArray",
           "ByteStream", "SerializedTreeFile"]


class STFBaseException(Exception, ABC):
    """
    Base for the entire hierarchy of exceptions
    """


class STFNonCriticalException(STFBaseException, ABC):
    """
    Base for fixable errors
    """


class STFCriticalException(STFBaseException, ABC):
    """
    Base for severe errors
    """


class STFMagicNumberException(STFCriticalException):
    """
    Indicates bad magic number
    """


class STFVersionException(STFCriticalException):
    """
    Indicates wrong version
    """


class STFUnboundStringException(STFCriticalException):
    """
    Unterminated String
    """


class STFOverRead(STFCriticalException):
    """
    Read too many bytes
    """


# pylint: disable=too-few-public-methods
class Configuration:
    """
    Stores relevant constants for the program, I hate magic numbers
    """
    # Default length of boolean values in bytes
    BOOL_LENGTH: int = 1
    # Maximum length of metadata in bytes
    METADATA_LENGTH: int = 3
    # Default string encoding
    ENCODING: str = "utf-8"
    # Whether to zero terminate strings
    ZERO_TERMINATE: bool = True
    # Maximum size of a subfield in bytes
    MAX_FIELD_SIZE: int = 4
    # Parity of data
    ENDIANNESS: Literal["little", "big"] = "big"
    # Size of ints in bytes
    INT_SIZE: int = 8
    # Magic number for validation
    MAGIC: int = 0xDEADBEEF
    # Version
    VERSION: int = 0x00000004


class Utility:
    """
    Stores utility functions
    """

    @staticmethod
    def mask_bits(length: int) -> int:
        """
        Filters the lower 'length' bits of an int
        """
        return (1 << length) - 1

    @staticmethod
    def version_validation(version: int) -> bool:
        """
        Checks if versions are compatible
        """
        return version == Configuration.VERSION

    @staticmethod
    def encode_nibbles(first: int, second: int) -> int:
        """
        Sticks two small ints into a byte
        """
        return ((first & 0x0F) << 4) | (second & 0x0F)

    @staticmethod
    def decode_nibbles(num: int) -> tuple[int, int]:
        """
        Pulls two small ints out of a byte
        """
        return (num & 0xF0) >> 4, num & 0x0F


class ByteStream(bytearray):
    """
    Subclass of the default bytearray that implements convenient
    methods for adding/reading values from a binary array
    """

    def __init__(self, initial_position: int = 0, old_array: bytearray | str = None) -> None:
        """
        Initializer
        """
        super().__init__()
        if old_array:
            # If a bytearray is passed, copy its data
            self.extend(old_array)
        self.__position: int = initial_position
        # self.__sub_position: int = 0

    def get_bytes(self) -> bytes:
        """
        Converts the ByteStream to bytes
        """
        return bytes(self)

    @property
    def position(self) -> int:
        """
        Current position in stream
        """
        return self.__position

    @property
    def remaining(self) -> "ByteStream":
        """
        Unread bytes
        """
        return ByteStream(old_array=self[self.__position:])

    @property
    def length(self) -> int:
        """
        Gets length of data
        """
        return len(self)

    @property
    def remaining_length(self) -> int:
        """
        Length of unread segment
        """
        return self.length - self.__position

    def read(self, length: int = 0) -> "ByteStream":
        """
        Reads bytes from the stream, errors if it reads past end, 0 read means read the rest.
        """
        new_position = self.__position + length
        # Check for over-read
        if new_position > self.length:
            raise STFOverRead(f"Read beyond length of data. Attempted to read {length} bytes starting at {self.position}, {new_position} > {self.length}")
        new_segment = ByteStream(old_array=self[self.__position: new_position])
        self.__position = new_position
        return new_segment

    def read_int(
            self,
            length: int = Configuration.INT_SIZE,
            byteorder: Literal["little", "big"] = Configuration.ENDIANNESS,
            signed: bool = False
    ) -> int:
        """
        Reads an integer
        """
        return int.from_bytes(bytes=self.read(length), byteorder=byteorder, signed=signed)

    def read_str(self, length: int = 0, encoding: str = Configuration.ENCODING) -> str:
        """
        Reads a string, zero terminated or not
        """
        if length > 0:
            return self.read(length).decode(encoding=encoding)
        try:
            zero_index = self.index(0x00, self.__position) - self.__position
        except ValueError as _:
            raise STFUnboundStringException from _
        result = self.read_str(zero_index)
        # Ignore zero
        self.read(1)
        return result

    def read_bool(self) -> bool:
        """
        Reads a bool
        """
        return bool(self.read(1))

    def write(self, data: bytearray | bytes) -> None:
        """
        Writes bytes
        """
        self.extend(data)

    def write_int(
            self,
            value: int,
            byteorder: Literal["little", "big"] = Configuration.ENDIANNESS,
            length: int = Configuration.INT_SIZE,
            signed: bool = False
    ) -> None:
        """
        Writes an int
        """
        self.write(value.to_bytes(length=length, byteorder=byteorder, signed=signed))

    def write_str(
            self,
            value: str,
            zero_terminated=Configuration.ZERO_TERMINATE,
            encoding: str = Configuration.ENCODING
    ) -> None:
        """
        Writes string
        """
        if zero_terminated:
            value += "\0"
        self.write(value.encode(encoding))

    def write_bool(
            self,
            value: bool,
            length: int = Configuration.BOOL_LENGTH,
            byteorder: Literal["little", "big"] = Configuration.ENDIANNESS,
            signed: bool = False
    ) -> None:
        """
        Writes a bool
        """
        self.write_int(value=value, length=length, byteorder=byteorder, signed=signed)

    # noinspection InsecureHash
    def hash(self) -> int:
        """
        Gets the sha256 hash of the ByteStream
        """
        hasher = hashlib.sha256()
        hasher.update(self)
        digest = hasher.digest()
        hashed = int.from_bytes(digest, Configuration.ENDIANNESS) & Utility.mask_bits(Configuration.INT_SIZE * 8)
        return hashed

    @classmethod
    def convert(cls, item: Any, *args, **kwargs):
        """
        Converts a miscellaneous data type to bytes
        """
        result = ByteStream()
        if isinstance(item, STFObject):
            result.write(item.serialize())
        elif isinstance(item, int):
            result.write_int(item, *args, **kwargs)
        elif isinstance(item, str):
            result.write_str(item, *args, **kwargs)
        elif isinstance(item, bool):
            result.write_bool(item, *args, **kwargs)
        else:
            raise TypeError(f"Unknown type {type(item).__name__}")
        return result

    def deconvert(self, *args, target_type: Type = object, **kwargs) -> Any:
        """
        Converts bytes to a type
        """
        if issubclass(target_type, STFObject):
            return target_type.deserialize(self)
        if issubclass(target_type, int):
            return self.read_int(*args, **kwargs)
        if issubclass(target_type, str):
            return self.read_str(*args, **kwargs)
        if issubclass(target_type, bool):
            return self.read_bool()
        raise TypeError(f"Unknown type {target_type.__name__}")

    def display(self, width: int = 8, index_start: int = 0) -> str:
        """
        Prints a hex dump of the bytes
        """
        result = str()
        for index, byte in enumerate(self[index_start:]):
            result += f"{byte:02x} "
            if index % width == width - 1:
                result += "\n"
        return result


class Header(NamedTuple):
    """
    Simple container for header info
    """
    hash: int
    size: int
    metadata: ByteStream = ByteStream()


class STFObject(ABC):
    """
    Interface class for STF format
    """
    MAX_FIELD_SIZE: int = 4
    MAX_METADATA_SIZE: int = 3
    requires_header: bool = True

    def serialize(self, *args, **kwargs) -> ByteStream:
        """
        Gets a binary representation of the object
        """
        result = ByteStream()
        if self.requires_header:
            result.write(self.header())
        result.write(self.data(*args, **kwargs))
        return result

    def header(self) -> ByteStream:
        """
        Gets the header from data
        """
        result = ByteStream()
        data = self.data()
        result.write_int(value=data.hash())
        result.write_int(value=data.length, length=self.MAX_FIELD_SIZE)
        #
        metadata: ByteStream = self.metadata()
        result.write_int(value=metadata.length, length=self.MAX_METADATA_SIZE)
        result.write(metadata)
        return result

    @classmethod
    def read_header(cls, data: ByteStream) -> Header:
        """
        Gets header from data
        """
        hashed: int = data.read_int()
        size: int = data.read_int(length=cls.MAX_FIELD_SIZE)
        metadata_length: int = data.read_int(length=cls.MAX_METADATA_SIZE)
        metadata: ByteStream = data.read(length=metadata_length)
        return Header(hashed, size, metadata)

    @classmethod
    @abstractmethod
    def deserialize(cls, data: ByteStream, *args, **kwargs) -> "STFObject":
        """
        Returns an object from bytes
        """

    @abstractmethod
    def data(self, *args, **kwargs) -> ByteStream:
        """
        Gets bytes of data
        """

    @abstractmethod
    def metadata(self) -> ByteStream:
        """
        Gets metadata
        """


class STFArray(list, STFObject, ABC):
    """
    Stores multiple of a single type
    """
    ELEM_FIELD_WIDTH: int = 2
    T: type = None

    @classmethod
    def deserialize(cls, data: ByteStream, *args, **kwargs) -> "STFObject":
        """
        Deserialize array
        """
        header = cls.read_header(data)
        num_elems = header.metadata.read_int(length=cls.ELEM_FIELD_WIDTH)
        result = cls(tuple())
        for _ in range(num_elems):
            result.append(data.deconvert(*args, target_type=cls.T, **kwargs))
        return cls(result)

    def data(self, *args, **kwargs) -> ByteStream:
        """
        Get array data
        """
        result = ByteStream()
        for item in self:
            result.write(ByteStream.convert(item, *args, **kwargs))
        return result

    def metadata(self) -> ByteStream:
        """
        Metadata includes number of elements
        """
        result = ByteStream()
        result.write_int(len(self), length=self.ELEM_FIELD_WIDTH)
        return result


class SerializedTreeFile:
    """
    Reads and writes objects to a tree
    """

    def __init__(self, filename: str, mode: str = "r") -> None:
        """
        Initializer
        """
        self.filename = filename
        self.mode = mode + 'b'
        self.file: BinaryIO

    def __enter__(self) -> "SerializedTreeFile":
        """
        Opens file
        """
        # pylint: disable=unspecified-encoding
        self.file = cast(BinaryIO, open(self.filename, self.mode))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Closes files
        """
        self.file.close()

    def write(self, obj: STFObject, *args, **kwargs) -> None:
        """
        Writes to file
        """
        data = ByteStream()
        data.write_int(Configuration.MAGIC, length=4)
        data.write_int(Configuration.VERSION, length=4)
        data.write(obj.serialize(*args, **kwargs))
        self.file.write(data.get_bytes())

    def read(self, target_type: Type[STFObject], *args, **kwargs) -> STFObject:
        """
        Reads object from file
        """
        data = ByteStream(old_array=bytearray(self.file.read()))
        magic = data.read_int(length=4)
        version = data.read_int(length=4)
        if magic != Configuration.MAGIC:
            raise STFMagicNumberException()
        if not Utility.version_validation(version):
            raise STFVersionException()
        return target_type.deserialize(data, *args, **kwargs)


# Testing


def main():
    """
    Entry point for testing
    """


if __name__ == "__main__":
    main()
