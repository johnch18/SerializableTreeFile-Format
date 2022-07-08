#!/usr/bin/python3.11


# Imports
from enum import Enum, auto
from stf import *
from typing import Iterable, Type
import random


__all__ = []


class Card(STFObject):
    class Suit(Enum):
        Hearts = 0
        Spades = auto()
        Clubs = auto()
        Diamonds = auto()

        @classmethod
        def get_random(cls) -> "Card.Suit":
            return Card.Suit(random.randint(0, 3))

    class Rank(Enum):
        Ace = 0
        Two = auto()
        Three = auto()
        Four = auto()
        Five = auto()
        Six = auto()
        Seven = auto()
        Eight = auto()
        Nine = auto()
        Ten = auto()
        Jack = auto()
        Queen = auto()
        King = auto()

        @classmethod
        def get_random(cls) -> "Card.Rank":
            return Card.Rank(random.randint(0, 13))

    def __init__(self, suit: Suit, rank: Rank) -> None:
        self.suit = suit
        self.rank = rank

    def __str__(self) -> str:
        return f"{self.rank.name} of {self.suit.name}"

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: "Card") -> bool:
        return self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))

    @classmethod
    def get_random(cls) -> "Card":
        return Card(Card.Suit.get_random(), Card.Rank.get_random())

    @classmethod
    def deserialize(cls, data: ByteStream, *args, **kwargs) -> "STFObject":
        header = cls.read_header(data)
        suit = Card.Suit(data.read_int(length=1))
        rank = Card.Rank(data.read_int(length=1))
        # print(name)
        return Card(suit, rank)

    def data(self, *args, **kwargs) -> ByteStream:
        result = ByteStream()
        result.write_int(self.suit.value, length=1)
        result.write_int(self.rank.value, length=1)
        return result

    @classmethod
    def get_all(cls) -> Iterable["Card"]:
        for suit in Card.Suit:
            for rank in Card.Rank:
                yield Card(suit, rank)

    def metadata(self) -> ByteStream:
        return ByteStream()


class Deck(STFArray):
    T: type = Card

    @classmethod
    def get_random(cls) -> "Deck":
        deck = list(Card.get_all())
        random.shuffle(deck)
        return Deck(deck)


def main():
    from pprint import pprint as pp
    deck = Deck.get_random()
    print("Before:")
    pp(deck)
    with SerializedTreeFile("deck.stf", "wb") as STF:
        STF.write(deck)
    with SerializedTreeFile("deck.stf", "rb") as STF:
        new_deck = STF.read(Deck)
    print("After:")
    pp(new_deck)


if __name__ == "__main__":
    main()
