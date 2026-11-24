

# Import-ant Libraries
from networkx import DiGraph
from re import search, sub
from random import randrange
from requests import head
from collections.abc import Iterable

async def omit_segments(sentence: str):

	words = sentence.split()

	heard_word_count = max(len(words) // 6, 2)

	heard_words_indexes = set()
	while heard_word_count > 0:
		insertion_point = randrange(len(words))

		for cluster_index in range(randrange(1, 3)):
			heard_words_indexes.add(insertion_point + cluster_index)
			heard_word_count -= 1

	for word_index in range(len(words)):

		if word_index in heard_words_indexes:
			continue

		word = words[word_index]
		if word == word.upper():
			continue
		else:
			words[word_index] = '...'

	return ' '.join(words)
