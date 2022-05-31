#!/usr/bin/python3.11


# Imports
from abc import ABC, abstractmethod
from typing import Iterable, NamedTuple, Any, Type, IO
import hashlib

__all__ = ["Configuration", "STFObject", "STFArray", "ByteStream", "SerializedTreeFile"]


def echo(functor):
    def wrap(*_, **__):
        r = functor(*_, **__)
        print(functor, _, __, ">", r)
        return r
    return wrap


class Configuration:
    BOOL_SIZE: int = 1
    METADATA_LENGTH: int = 3
    ENCODING: str = "utf-8"
    ZERO_TERMINATE: bool = True
    MAX_FIELD_SIZE: int = 4
    ENDIANNESS: str = "big"
    INT_SIZE: int = 8
    MAGIC: int = 0xDEADBEEF
    VERSION: int = 0x00000003

    @classmethod
    def MASK(cls, length: int) -> int:
        return (1 << length) - 1


class ByteStream(bytearray):
    def __init__(self, *args, initial_position: int = 0, old_array: bytearray = None, **kwargs):
        super().__init__(self, *args, **kwargs)
        if old_array:
            self.extend(old_array)
        self.__dirty = True
        self.__position = initial_position

    def position(self) -> int:
        return self.__position

    def remaining(self) -> "ByteStream":
        return ByteStream(old_array=self[self.__position:])

    def length(self) -> int:
        return len(self)

    def remaining_length(self) -> int:
        return self.length - self.__position

    def append(self, item: int) -> None:
        self.mark_dirty()
        super().append(item)

    def extend(self, data: Iterable[int]) -> None:
        self.mark_dirty()
        super().extend(data)

    # @echo
    def read(self, length: int = 0) -> "ByteStream":
        self.mark_dirty()
        new_position = self.__position + length
        if new_position > self.length():
            raise IndexError(f"Read beyond length of data. Attempted to read {length} bytes starting at {self.position()}, {new_position} > {self.length()}")
        new_segment = ByteStream(old_array=self[self.__position: new_position])
        self.__position = new_position
        return new_segment

    def read_int(self, length: int = Configuration.INT_SIZE, byteorder: str = Configuration.ENDIANNESS, signed: bool = False):
        return int.from_bytes(bytes=self.read(length), byteorder=byteorder, signed=signed)

    def read_str(self, length: int = 0, encoding: str = Configuration.ENCODING):
        if length > 0:
            return self.read(length).decode(encoding=encoding)
        else:
            zero_index = self.index(0x00, self.__position) - self.__position
            s = self.read_str(zero_index)
            self.read(1)
            return s

    def read_bool(self) -> bool:
        return bool(self.read(1))

    def write(self, data: bytearray) -> None:
        self.extend(data)

    def write_int(self, value: int, byteorder: str = Configuration.ENDIANNESS, length: int = Configuration.INT_SIZE, signed: bool = False) -> None:
        self.write(value.to_bytes(length=length, byteorder=byteorder, signed=signed))

    def write_str(self, value: str, zero_terminated=Configuration.ZERO_TERMINATE, encoding: str = Configuration.ENCODING) -> None:
        if zero_terminated:
            value += "\0"
        self.write(value.encode(encoding))

    def write_bool(self, value: bool, length: int = Configuration.BOOL_SIZE, byteorder: str = Configuration.ENDIANNESS, signed: bool = False) -> None:
        self.write_int(value=value, length=length, byteorder=byteorder, signed=signed)

    def mark_dirty(self) -> None:
        self.__dirty = True

    def mark_clean(self) -> None:
        self.__dirty = False

    def dirty(self) -> bool:
        return self.__dirty

    # noinspection InsecureHash
    def hash(self) -> int:
        hasher = hashlib.sha256()
        hasher.update(self)
        digest = hasher.digest()
        hashed = int.from_bytes(digest, Configuration.ENDIANNESS) & Configuration.MASK(Configuration.INT_SIZE * 8)
        return hashed

    @classmethod
    def convert(cls, item: Any, *args, **kwargs):
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

    def deconvert(self, T: Type = object, *args, **kwargs) -> Any:
        if issubclass(T, STFObject):
            return T.deserialize(self)
        elif issubclass(T, int):
            return self.read_int(*args, **kwargs)
        elif issubclass(T, str):
            return self.read_str(*args, **kwargs)
        elif issubclass(T, bool):
            return self.read_bool()
        else:
            raise TypeError(f"Unknown type {T.__name__}")

    def display(self, width: int = 8, index: int = 0) -> str:
        result = str()
        i = 0
        for b in self[index:]:
            result += f"{b:02x} "
            if i % width == width - 1:
                result += "\n"
            i += 1
        return result


class Header(NamedTuple):
    hash: int
    size: int
    metadata: ByteStream = ByteStream()


class STFObject(ABC):
    def serialize(self, *args, **kwargs) -> ByteStream:
        result = ByteStream()
        result.write(self.header())
        result.write(self.data(*args, **kwargs))
        return result

    def header(self) -> ByteStream:
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
        hashed: int = data.read_int()
        size: int = data.read_int(length=Configuration.MAX_FIELD_SIZE)
        metadata_length: int = data.read_int(length=Configuration.METADATA_LENGTH)
        metadata: ByteStream = data.read(length=metadata_length)
        return Header(hashed, size, metadata)

    @classmethod
    @abstractmethod
    def deserialize(cls, data: ByteStream, *args, **kwargs) -> "STFObject":
        pass

    @abstractmethod
    def data(self, *args, **kwargs) -> ByteStream:
        pass

    def metadata(self) -> ByteStream:
        return ByteStream()


class STFArray(list, STFObject):
    MAX_ELEMS: int = 2

    def __init__(self, iterable: Iterable[Any], T: Type = object) -> None:
        super().__init__(iterable)
        self.__T = T

    @classmethod
    def deserialize(cls, data: ByteStream, *args, T: Type = object, **kwargs) -> "STFObject":
        header = cls.read_header(data)
        num_elems = header.metadata.read_int(length=STFArray.MAX_ELEMS)
        result = STFArray(iterable=tuple(), T=T)
        for i in range(num_elems):
            result.append(data.deconvert(*args, T=T, **kwargs))
        return result

    def data(self, *args, **kwargs) -> ByteStream:
        result = ByteStream()
        for item in self:
            result.write(ByteStream.convert(item, *args, **kwargs))
        return result

    def metadata(self) -> ByteStream:
        result = ByteStream()
        result.write_int(len(self), length=STFArray.MAX_ELEMS)
        return result


class SerializedTreeFile:
    def __init__(self, filename: str, mode: str = "rb") -> None:
        self.filename = filename
        self.mode = mode
        self.file: IO = None

    def __enter__(self) -> "SerializedTreeFile":
        self.file = open(self.filename, self.mode)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.file.close()

    def write(self, obj: STFObject, *args, **kwargs) -> None:
        data = ByteStream()
        data.write_int(Configuration.MAGIC, length=4)
        data.write_int(Configuration.VERSION, length=4)
        data.write(obj.serialize(*args, **kwargs))
        self.file.write(data)

    def read(self, T: Type[STFObject], *args, **kwargs) -> STFObject:
        data = ByteStream(old_array=self.file.read())
        magic = data.read_int(length=4)
        version = data.read_int(length=4)
        if magic != Configuration.MAGIC:
            raise Exception("Incorrect Magic Number")
        if version != Configuration.VERSION:
            raise Exception("Incorrect Version")
        return T.deserialize(data, *args, **kwargs)


# Testing


def main():
    with SerializedTreeFile("test.stf", "wb") as stf:
        pass


if __name__ == "__main__":
    main()
