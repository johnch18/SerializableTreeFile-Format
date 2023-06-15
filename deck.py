#!/usr/bin/python3.11

"""
A test example for STF
"""


# Imports
import random
from typing import Iterable
from enum import Enum, auto

import stf

__all__ = []


class Card(stf.STFObject):
    """
    A card object
    """

    def metadata(self) -> stf.ByteStream:
        """
        Gets metadata
        """
        return stf.ByteStream()

    requires_header = False

    class Suit(Enum):
        """
        A suit
        """
        HEARTS = 0
        SPADES = auto()
        CLUBS = auto()
        DIAMONDS = auto()

        @classmethod
        def get_random(cls) -> "Card.Suit":
            """
            Gets a random suit
            """
            return Card.Suit(random.randint(0, 3))

    class Rank(Enum):
        """
        Rank of a card
        """

        ACE = 0
        TWO = auto()
        THREE = auto()
        FOUR = auto()
        FIVE = auto()
        SIX = auto()
        SEVEN = auto()
        EIGHT = auto()
        NINE = auto()
        TEN = auto()
        JACK = auto()
        QUEEN = auto()
        KING = auto()

        @classmethod
        def get_random(cls) -> "Card.Rank":
            """
            Gets a random card rank
            """
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
        """
        Creates a random card
        """
        return Card(Card.Suit.get_random(), Card.Rank.get_random())

    @classmethod
    def deserialize(cls, data: stf.ByteStream, *_, **__) -> "stf.STFObject":
        """
        Deserializes a card
        """
        suit = Card.Suit(data.read_int(length=1))
        rank = Card.Rank(data.read_int(length=1))
        return Card(suit, rank)

    def data(self, *_, **__) -> stf.ByteStream:
        """
        Gets the data for serialization
        """
        result = stf.ByteStream()
        result.write_int(self.suit.value, length=1)
        result.write_int(self.rank.value, length=1)
        return result

    @classmethod
    def get_all(cls) -> Iterable["Card"]:
        """
        Get all cards
        """
        for suit in Card.Suit:
            for rank in Card.Rank:
                yield Card(suit, rank)


# pylint: disable=too-few-public-methods
class Deck(stf.STFArray):
    """
    An implementation of an STFArray
    """
    T: type = Card

    @classmethod
    def get_random(cls) -> "Deck":
        """
        Gets a random deck
        """
        deck = list(Card.get_all())
        random.shuffle(deck)
        return Deck(deck)


def main():
    """
    Test method
    """
    deck = Deck.get_random()
    print(deck)
    with stf.SerializedTreeFile("deck.stf", "wb") as deck_in:
        deck_in.write(deck)
    #
    with stf.SerializedTreeFile("deck.stf", "rb") as deck_out:
        new_deck = deck_out.read(Deck)
    print(new_deck)


if __name__ == "__main__":
    main()
