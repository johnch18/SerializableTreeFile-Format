#!/usr/bin/python3.11


import hashlib
# Imports
from abc import ABC, abstractmethod
from typing import NamedTuple, Any, Type, IO

__all__ = ["Configuration", "STFObject", "STFArray", "ByteStream", "SerializedTreeFile"]


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
    ENDIANNESS: str = "big"
    # Size of ints in bytes
    INT_SIZE: int = 8
    # Magic number for validation
    MAGIC: int = 0xDEADBEEF
    # Version
    VERSION: int = 0x00000003

    @classmethod
    def mask_bits(cls, length: int) -> int:
        """
        Filters the lower 'length' bits of an int
        """
        return (1 << length) - 1


class ByteStream(bytearray):
    """
    Subclass of the default bytearray that implements convenient
    methods for adding/reading values from a binary array
    """

    def __init__(self, *args, initial_position: int = 0, old_array: bytearray = None, **kwargs):
        """
        Initializer
        """
        super().__init__(self, *args, **kwargs)
        if old_array:
            # If a bytearray is passed, copy its data
            self.extend(old_array)
        self.__position = initial_position

    def position(self) -> int:
        """
        Current position in stream
        """
        return self.__position

    def remaining(self) -> "ByteStream":
        """
        Unread bytes
        """
        return ByteStream(old_array=self[self.__position:])

    def length(self) -> int:
        """
        Gets length of data
        """
        return len(self)

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
        if new_position > self.length():
            raise IndexError(f"Read beyond length of data. Attempted to read {length} bytes" \
                             " starting at {self.position()}, {new_position} > {self.length()}")
        new_segment = ByteStream(old_array=self[self.__position: new_position])
        self.__position = new_position
        return new_segment

    def read_int(
            self,
            length: int = Configuration.INT_SIZE,
            byteorder: str = Configuration.ENDIANNESS,
            signed: bool = False
    ):
        """
        Reads an integer
        """
        return int.from_bytes(bytes=self.read(length), byteorder=byteorder, signed=signed)

    def read_str(self, length: int = 0, encoding: str = Configuration.ENCODING):
        """
        Reads a string, zero terminated or not
        """
        if length > 0:
            return self.read(length).decode(encoding=encoding)
        zero_index = self.index(0x00, self.__position) - self.__position
        result = self.read_str(zero_index)
        # Ignore zero
        self.read(1)
        return result

    def read_bool(self) -> bool:
        """
        Reads a bool
        """
        return bool(self.read(1))

    def write(self, data: bytearray) -> None:
        """
        Writes bytes
        """
        self.extend(data)

    def write_int(
            self,
            value: int,
            byteorder: str = Configuration.ENDIANNESS,
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
            byteorder: str = Configuration.ENDIANNESS,
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
        hashed = int.from_bytes(digest, Configuration.ENDIANNESS) &\
                 Configuration.mask_bits(Configuration.INT_SIZE * 8)
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

    def deconvert(self,  *args, target_type: Type = object, **kwargs) -> Any:
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

    def display(self, width: int = 8, index: int = 0) -> str:
        """
        Prints a hex dump of the bytes
        """
        result = str()
        i = 0
        for byte in self[index:]:
            result += f"{byte:02x} "
            if i % width == width - 1:
                result += "\n"
            i += 1
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

    def serialize(self, *args, **kwargs) -> ByteStream:
        """
        Gets a binary representation of the object
        """
        result = ByteStream()
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
        result.write_int(value=data.length(), length=Configuration.MAX_FIELD_SIZE)
        #
        metadata: ByteStream = self.metadata()
        result.write_int(value=metadata.length(), length=Configuration.METADATA_LENGTH)
        result.write(metadata)
        return result

    @classmethod
    def read_header(cls, data: ByteStream) -> Header:
        """
        Gets header from data
        """
        hashed: int = data.read_int()
        size: int = data.read_int(length=Configuration.MAX_FIELD_SIZE)
        metadata_length: int = data.read_int(length=Configuration.METADATA_LENGTH)
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

    def metadata(self) -> ByteStream:
        """
        Gets metadata
        """
        return ByteStream()


class STFArray(list, STFObject, ABC):
    """
    Stores multiple of a single type
    """
    MAX_ELEMS: int = 2
    T: type = None

    @classmethod
    def deserialize(cls, data: ByteStream, *args, **kwargs) -> "STFObject":
        """
        Deserialize array
        """
        header = cls.read_header(data)
        num_elems = header.metadata.read_int(length=STFArray.MAX_ELEMS)
        result = cls(iterable=tuple())
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
        result.write_int(len(self), length=STFArray.MAX_ELEMS)
        return result


class SerializedTreeFile:
    """
    Reads and writes objects to a tree
    """

    def __init__(self, filename: str, mode: str = "rb") -> None:
        """
        Initializer
        """
        self.filename = filename
        self.mode = mode
        self.file: IO = None

    def __enter__(self) -> "SerializedTreeFile":
        """
        Opens file
        """
        self.file = open(self.filename, self.mode, encoding=Configuration.ENCODING)
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
        self.file.write(data)

    def read(self, target_type: Type[STFObject], *args, **kwargs) -> STFObject:
        """
        Reads object from file
        """
        data = ByteStream(old_array=self.file.read())
        magic = data.read_int(length=4)
        version = data.read_int(length=4)
        if magic != Configuration.MAGIC:
            raise Exception("Incorrect Magic Number")
        if version != Configuration.VERSION:
            raise Exception("Incorrect Version")
        return target_type.deserialize(data, *args, **kwargs)


# Testing


def main():
    """
    Entry point for testing
    """


if __name__ == "__main__":
    main()
