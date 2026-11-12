# E7: two different messages, same Internet checksum.
def checksum(words):
    s = sum(words)
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF

a = [0x1234, 0x0001, 0x0000, 0xABCD]
b = [0x1233, 0x0002, 0x0000, 0xABCD]   # one word down by 1, another up by 1
print(hex(checksum(a)), hex(checksum(b)))
