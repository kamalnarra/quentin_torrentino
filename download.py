import math
import heapq
import hashlib
import random
from utils import pretty_print
import time
import asyncio

BLOCK_LENGTH = 2**14


class DownloadHandler:
    def __init__(self, tracker, torrent):
        self.tracker = tracker
        self.needed_pieces = []
        self.pending_pieces = []
        self.finished_pieces = []
        self.torrent = torrent
        self.start_time = time.time()  # record the start time of the download
        self.total_size = torrent.tracker.length  # total file size
        self.init_pieces()

    # function below verifies that each piece's hash matches the hash in the torrent file

    def init_pieces(self):
        piece_length = self.tracker.piece_length
        for piece_num in range(0, self.tracker.num_pieces):
            hash = self.tracker.pieces[(20 * piece_num) : (20 * piece_num) + 20]
            if piece_num < (self.tracker.blocks_per_piece - 1):
                piece = Piece(
                    hash, piece_length, self.tracker.blocks_per_piece, piece_num
                )
            else:
                last_piece_length = 0
                if self.tracker.length % piece_length > 0:
                    last_piece_length = self.tracker.length % piece_length
                else:
                    last_piece_length = self.tracker.piece_length
                num_blocks_per_last_piece = math.ceil(last_piece_length / 2**14)
                piece = Piece(
                    hash, last_piece_length, num_blocks_per_last_piece, piece_num
                )
            self.needed_pieces.append([piece, 0])
        random.shuffle(self.needed_pieces)

    def handle_have(self, piece_index):
        if piece_index < self.tracker.num_pieces:
            l = [x for x in self.needed_pieces if x[0].index == piece_index]
            if len(l):
                l[0][1] += 1

    # for avg download speed
    def format_size(self, size):
        units = ["B", "KB", "MB", "GB", "TB"]
        unit = 0
        while size >= 1024:
            size /= 1024
            unit += 1
        return f"{size:.2f}{units[unit]}"

    def get_avg_speed(self):
        elapsed_time = time.time() - self.start_time  # total time taken
        average_speed = (
            self.total_size / elapsed_time
        )  # calculate average speed in bytes/second
        return average_speed

    def next(self, pieces):
        if len(self.pending_pieces):
            return self.pending_pieces.pop(0)
        filtered = [x for x in self.needed_pieces if x[0].index in pieces]
        if len(filtered) == 0:
            return None
        top = min(filtered, key=lambda x: x[1])  # pick highest rarity
        self.needed_pieces.remove(top)
        return top[0]

    def check_done(self):
        if (
            len(self.pending_pieces)
            or len(self.needed_pieces)
            or len([x for x in self.torrent.peer_list if x.waiting])
        ):
            return

        avg_speed = self.get_avg_speed()
        pretty_print("DOWNLOAD FINISHED 🥳🥳🥳", "green")

        # TODO: once it is fully downloaded we then
        # check compare each piece's hash to the hash in the torrent file
        # if they match, then the file is downloaded correctly

        self.torrent.filewriter.file.close()
        pretty_print(
            f"Average download speed: {self.format_size(avg_speed)}/s", "green"
        )


class Piece:
    def __init__(self, hash, length, num_blocks, index):
        self.downloaded = False
        self.index = index
        self.offset = 0
        self.hash = hash
        self.actual_hash = hashlib.sha1()
        self.length = length
        self.num_blocks = num_blocks

    def next_block_length(self):
        if self.offset + BLOCK_LENGTH <= self.num_blocks * BLOCK_LENGTH:
            return BLOCK_LENGTH
        elif self.length - self.offset > 0:
            return self.length - self.offset
        else:
            return None


class FileWriter:
    def __init__(self, filename, torrent):
        self.filename = filename
        pretty_print(f"NAME OF FILE: {filename}", "green")

        self.total_size = torrent.tracker.length
        self.piece_length = torrent.tracker.piece_length
        self.file = open(filename, "wb")
        self.torrent = torrent
        self.pieces = [
            False for _ in range(-(-self.total_size // self.piece_length))
        ]  # ceil division
        # total_size // piece_length

    def write_block(self, piece_index, block_index, block_data):
        position = piece_index * self.piece_length + block_index
        self.file.seek(position)
        self.file.write(block_data)
        self.pieces[piece_index] = True  # mark piece as downloaded

    def read_piece(self, index, begin, length):
        # Open the file in binary mode
        with open(self.filename, 'rb') as file:
            # Seek to the correct position in the file
            file.seek(index * self.piece_length + begin)

            # Read the requested data
            piece_data = file.read(length)

        return piece_data
    

    def get_bitfield(self):
        bitfield = bytearray()
        for i in range(0, len(self.pieces), 8):
            byte = 0
            for j in range(8):
                if i + j < len(self.pieces) and self.pieces[i + j]:
                    byte |= 1 << (7 - j)
            bitfield.append(byte)
        return bytes(bitfield)

    def close(self):
        self.file.close()
