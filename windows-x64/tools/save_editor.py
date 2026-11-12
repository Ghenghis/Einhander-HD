#!/usr/bin/env python3
"""Einhander memory-card save editor (PSX .mcd files, 128 KiB).

Commands:
    list   <card.mcd>                 list directory blocks
    inject <card.mcd> [slot] [name]   write a valid Einhander save block
    rename <card.mcd> <slot> <name>   rewrite product-code name in dir entry
    delete <card.mcd> <slot>          mark dir entry free (chain-aware)

PSX card layout: sector 0 header "MC", sectors 1-15 = 128-byte directory
frames, sectors 16-35 = broken-frame list, data blocks (8192 B each) start
at sector 64. Einhander product code: BASCUS-94243.
"""
import sys
import os

CARD = 131072
SECTOR = 128
BLOCK = 8192
DIR_SECTORS = 15
DATA_START = 64 * SECTOR          # 0x2000
PRODUCT = b"BASCUS-94243"
TITLE = "EINHANDER"


def xsum(b: bytes) -> int:
    x = 0
    for c in b:
        x ^= c
    return x


def load(p):
    d = bytearray(open(p, "rb").read())
    if len(d) != CARD or d[:2] != b"MC":
        print("not a formatted PSX memory card:", p)
        sys.exit(1)
    return d


def save(p, d):
    open(p, "wb").write(bytes(d))


def dir_frame(d, i):
    off = SECTOR * (1 + i)
    return d[off:off + SECTOR]


def status_of(d, i):
    return dir_frame(d, i)[0]


def list_blocks(p):
    d = load(p)
    print(f"{p}  blocks:")
    for i in range(DIR_SECTORS):
        f = dir_frame(d, i)
        st = f[0]
        size = int.from_bytes(f[4:8], "little")
        nxt = int.from_bytes(f[8:10], "little")
        code = f[10:30].rstrip(b"\x00").decode("ascii", "replace")
        ok = "OK" if f[127] == xsum(f[:127]) else "BAD-CSUM"
        tag = {0x51: "HEAD ", 0x52: "MID  ", 0x53: "END  ",
               0xA0: "free "}.get(st & 0xF0 and st, f"0x{st:02X}")
        print(f"  [{i:02d}] {tag} size={size:5d} next={nxt:04X} "
              f"{ok:8s} {code}")


def make_dir_entry(name_ascii: str, blocks: int = 1,
                   status: int = 0x51) -> bytes:
    f = bytearray(SECTOR)
    f[0] = status
    f[4:8] = (BLOCK * blocks).to_bytes(4, "little")
    f[8:10] = b"\xff\xff"                      # last block in chain
    code = (PRODUCT + name_ascii.encode("ascii"))[:20]
    f[10:10 + len(code)] = code                # product + file name
    f[127] = xsum(f[:127])
    return bytes(f)


def make_title_frame(name_ascii: str, blocks: int = 1) -> bytes:
    """First sector of a save block: SC + icon flag + block count + title."""
    f = bytearray(SECTOR)
    f[0:2] = b"SC"
    f[2] = 0x11                                # 1-frame icon, 16-color
    f[3] = blocks
    title = TITLE.ljust(64, " ").encode("shift_jis", "replace")
    f[4:68] = title
    return bytes(f)


def make_data_frame(name_ascii: str) -> bytes:
    """Second sector of the block: region product code + game data header."""
    f = bytearray(SECTOR)
    code = (b"SCUS-94243" + name_ascii.encode("ascii"))[:28]
    f[0:len(code)] = code
    return bytes(f)


def inject(p, slot=0, name="EINHANDER"):
    d = load(p)
    slot = int(slot)
    if not (0 <= slot < DIR_SECTORS):
        print("slot must be 0-14")
        sys.exit(1)
    st = status_of(d, slot)
    if st != 0xA0:
        print(f"slot {slot} busy (status 0x{st:02X}); delete it first")
        sys.exit(1)
    # directory entry
    d[SECTOR * (1 + slot):SECTOR * (2 + slot)] = make_dir_entry(name)
    # data block: 64 sectors starting at DATA_START + slot*BLOCK
    boff = DATA_START + slot * BLOCK
    d[boff:boff + SECTOR] = make_title_frame(name)
    d[boff + SECTOR:boff + 2 * SECTOR] = make_data_frame(name)
    # remaining icon area + data zeros already 0x00; leave as-is
    save(p, d)
    print(f"injected Einhander block '{name}' into slot {slot}")
    list_blocks(p)


def rename(p, slot, name):
    d = load(p)
    slot = int(slot)
    f = bytearray(dir_frame(d, slot))
    if f[0] not in (0x51, 0x52, 0x53):
        print(f"slot {slot} is not a used block")
        sys.exit(1)
    code = (PRODUCT + name.encode("ascii"))[:20]
    f[10:30] = bytes(20)
    f[10:10 + len(code)] = code
    f[127] = xsum(f[:127])
    d[SECTOR * (1 + slot):SECTOR * (2 + slot)] = bytes(f)
    save(p, d)
    print(f"slot {slot} renamed -> {code.decode()}")


def delete(p, slot):
    d = load(p)
    slot = int(slot)
    f = bytearray(dir_frame(d, slot))
    if f[0] == 0xA0:
        print(f"slot {slot} already free")
        return
    f = bytearray(SECTOR)
    f[0] = 0xA0
    f[8:10] = b"\xff\xff"
    f[127] = xsum(f[:127])
    d[SECTOR * (1 + slot):SECTOR * (2 + slot)] = bytes(f)
    save(p, d)
    print(f"slot {slot} freed")


USAGE = __doc__
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)
    op, path = sys.argv[1], sys.argv[2]
    if op == "list":
        list_blocks(path)
    elif op == "inject":
        inject(path,
               sys.argv[3] if len(sys.argv) > 3 else 0,
               sys.argv[4] if len(sys.argv) > 4 else "EINHANDER")
    elif op == "rename":
        rename(path, sys.argv[3], sys.argv[4])
    elif op == "delete":
        delete(path, sys.argv[3])
    else:
        print(USAGE)
