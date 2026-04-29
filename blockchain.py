import hashlib
import json
from datetime import datetime
from database import get_db, add_block, get_all_blocks


class Block:
    def __init__(self, index, voter_id, candidate, constituency,
                 timestamp=None, previous_hash="0"):
        self.index = index
        self.voter_id = voter_id
        self.candidate = candidate
        self.constituency = constituency
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        self.previous_hash = previous_hash
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_data = json.dumps({
            "index": self.index,
            "voter_id": self.voter_id,
            "candidate": self.candidate,
            "constituency": self.constituency,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash
        }, sort_keys=True)
        return hashlib.sha256(block_data.encode()).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "voter_id": self.voter_id,
            "candidate": self.candidate,
            "constituency": self.constituency,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "hash": self.hash
        }


class Blockchain:
    def __init__(self, election_id="ELECTION_1"):
        self.election_id = election_id
        self.chain = []
        self._load_from_db()

    def _load_from_db(self):
        conn = get_db()
        db_blocks = get_all_blocks(conn, self.election_id)
        conn.close()

        if not db_blocks:
            self._create_genesis_block()
        else:
            for b in db_blocks:
                block = Block(
                    index=b["block_index"],
                    voter_id=b["voter_id"],
                    candidate=b["candidate"],
                    constituency=b["constituency"],
                    timestamp=b["timestamp"],
                    previous_hash=b["previous_hash"]
                )
                block.hash = b["hash"]  # Trust DB hash
                self.chain.append(block)

    def _create_genesis_block(self):
        genesis = Block(index=0, voter_id="GENESIS", candidate="NONE",
                        constituency="GENESIS",
                        timestamp=datetime.utcnow().isoformat(),
                        previous_hash="0")
        self.chain.append(genesis)
        conn = get_db()
        add_block(conn, genesis, self.election_id)
        conn.close()

    @property
    def last_block(self):
        return self.chain[-1]

    def add_vote(self, voter_id, candidate, constituency):
        block = Block(
            index=len(self.chain),
            voter_id=voter_id,
            candidate=candidate,
            constituency=constituency,
            previous_hash=self.last_block.hash
        )
        self.chain.append(block)
        conn = get_db()
        add_block(conn, block, self.election_id)
        conn.close()
        return block

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
        return True

    def get_results(self):
        results = {}
        for block in self.chain[1:]:
            results[block.candidate] = results.get(block.candidate, 0) + 1
        return results

    def get_results_by_constituency(self):
        by_c = {}
        for block in self.chain[1:]:
            c = block.constituency
            if c not in by_c:
                by_c[c] = {}
            by_c[c][block.candidate] = by_c[c].get(block.candidate, 0) + 1
        return by_c

    def get_chain_data(self):
        return [b.to_dict() for b in self.chain]

    def has_voted(self, voter_id):
        return any(b.voter_id == voter_id for b in self.chain[1:])
