# Tech by Math, Git tutorial 8, exercise E7: compute a tree's id by hand, from the ids of what it lists.
# Raw tree format: for each entry, "<mode> <name>\0" then the 20 raw bytes of the id; entries sorted by name.
import hashlib


def tree_id(entries):
    body = b"".join(mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(oid) for mode, name, oid in entries)
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


# The root tree of the second commit in ex01.out.txt (git stores a directory's mode as 40000, no leading 0)
root = [("100644", "README", "ea2ae6d3d7f82720f73a3ef28c653d220772a40e"),
        ("40000", "docs", "269d5682f356e77b9b0bff0b7b8414a895b74be4")]
print("computed root tree id:", tree_id(root))
print("git's root tree id:    d6c0913970589432f4ab74acf8b614dac9fda8cc  (ex01.out.txt, 'tree' line of the second commit)")
