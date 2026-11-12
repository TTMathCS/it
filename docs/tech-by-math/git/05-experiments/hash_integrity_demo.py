#!/usr/bin/env python3
"""
Git Hash Integrity Demonstration
Demonstrates how Git ensures data integrity through cryptographic hashing
"""

import hashlib
import os
import tempfile


def git_hash_object(obj_type, content):
    """Compute Git object hash exactly like git hash-object"""
    header = f"{obj_type} {len(content)}\0"
    full_data = (header + content).encode('utf-8')
    return hashlib.sha1(full_data).hexdigest()


def demonstrate_hash_properties():
    """Show key properties of Git's hash function"""
    print("=== Git Hash Function Properties ===\n")
    
    # 1. Deterministic
    content = "Hello, Git!"
    hash1 = git_hash_object("blob", content)
    hash2 = git_hash_object("blob", content)
    print(f"1. DETERMINISTIC: Same input produces same hash")
    print(f"   Content: '{content}'")
    print(f"   Hash 1:  {hash1}")
    print(f"   Hash 2:  {hash2}")
    print(f"   Equal:   {hash1 == hash2}\n")
    
    # 2. Avalanche Effect
    content_a = "Hello, Git!"
    content_b = "Hello, Git?"
    hash_a = git_hash_object("blob", content_a)
    hash_b = git_hash_object("blob", content_b)
    print(f"2. AVALANCHE EFFECT: Small change, big hash difference")
    print(f"   Content A: '{content_a}'")
    print(f"   Hash A:    {hash_a}")
    print(f"   Content B: '{content_b}'")
    print(f"   Hash B:    {hash_b}")
    print(f"   Different: {hash_a != hash_b}\n")
    
    # 3. Content Addressing
    print(f"3. CONTENT ADDRESSING: Hash identifies content uniquely")
    test_files = {
        "README.md": "# My Project\nThis is awesome!",
        "main.py": "print('Hello, World!')",
        "config.json": '{"version": "1.0", "debug": true}'
    }
    
    for filename, content in test_files.items():
        hash_val = git_hash_object("blob", content)
        print(f"   {filename:12} -> {hash_val}")


def demonstrate_integrity_verification():
    """Show how Git detects data corruption"""
    print("\n=== Integrity Verification ===\n")
    
    original_content = "def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
    original_hash = git_hash_object("blob", original_content)
    
    print("Original file:")
    print(f"Content: {original_content[:50]}...")
    print(f"Hash:    {original_hash}")
    
    # Simulate corruption
    corrupted_content = original_content.replace("fibonacci", "fibonaci")  # typo
    corrupted_hash = git_hash_object("blob", corrupted_content)
    
    print("\nAfter corruption:")
    print(f"Content: {corrupted_content[:50]}...")
    print(f"Hash:    {corrupted_hash}")
    
    print(f"\nCorruption detected: {original_hash != corrupted_hash}")
    
    # Show how to verify integrity
    def verify_integrity(expected_hash, content):
        actual_hash = git_hash_object("blob", content)
        return actual_hash == expected_hash
    
    print(f"Integrity check (original):  {verify_integrity(original_hash, original_content)}")
    print(f"Integrity check (corrupted): {verify_integrity(original_hash, corrupted_content)}")


def demonstrate_collision_resistance():
    """Show collision resistance properties"""
    print("\n=== Collision Resistance Demo ===\n")
    
    # Generate many different contents and show unique hashes
    contents = [
        "Version 1.0.0",
        "Version 1.0.1", 
        "Version 1.1.0",
        "Version 2.0.0",
        f"Random content {os.urandom(10).hex()}",
        f"Another random {os.urandom(10).hex()}",
        "The quick brown fox jumps over the lazy dog",
        "The quick brown fox jumps over the lazy dog.",  # Added period
    ]
    
    hashes = {}
    for content in contents:
        hash_val = git_hash_object("blob", content)
        hashes[hash_val] = content
        print(f"'{content[:30]:30}' -> {hash_val}")
    
    print(f"\nGenerated {len(contents)} contents -> {len(hashes)} unique hashes")
    print(f"No collisions found: {len(contents) == len(hashes)}")


def demonstrate_merkle_tree_concept():
    """Simple demonstration of Merkle tree-like structure"""
    print("\n=== Merkle Tree Structure Demo ===\n")
    
    # Simulate a simple directory tree
    files = {
        "src/main.py": "print('Hello, World!')",
        "src/utils.py": "def helper(): return True",
        "README.md": "# My Project",
        "LICENSE": "MIT License"
    }
    
    # Hash individual files (like Git blobs)
    file_hashes = {}
    for filename, content in files.items():
        hash_val = git_hash_object("blob", content)
        file_hashes[filename] = hash_val
        print(f"FILE: {filename:15} -> {hash_val}")
    
    # Create tree hash (simplified - real Git is more complex)
    src_tree_content = "".join([
        f"100644 main.py\0{file_hashes['src/main.py']}",
        f"100644 utils.py\0{file_hashes['src/utils.py']}"
    ])
    src_tree_hash = git_hash_object("tree", src_tree_content)
    
    root_tree_content = "".join([
        f"040000 src\0{src_tree_hash}",
        f"100644 README.md\0{file_hashes['README.md']}",
        f"100644 LICENSE\0{file_hashes['LICENSE']}"
    ])
    root_tree_hash = git_hash_object("tree", root_tree_content)
    
    print(f"\nTREE: src/              -> {src_tree_hash}")
    print(f"TREE: root              -> {root_tree_hash}")
    
    print("\nMerkle Property: Change any file -> Root hash changes")
    
    # Modify one file
    modified_files = files.copy()
    modified_files["src/main.py"] = "print('Hello, Modified World!')"
    
    # Recalculate hashes
    new_main_hash = git_hash_object("blob", modified_files["src/main.py"])
    new_src_tree_content = src_tree_content.replace(file_hashes['src/main.py'], new_main_hash)
    new_src_tree_hash = git_hash_object("tree", new_src_tree_content)
    new_root_tree_content = root_tree_content.replace(src_tree_hash, new_src_tree_hash)
    new_root_tree_hash = git_hash_object("tree", new_root_tree_content)
    
    print(f"\nAfter modifying src/main.py:")
    print(f"New root hash:          -> {new_root_tree_hash}")
    print(f"Root hash changed:      -> {root_tree_hash != new_root_tree_hash}")


if __name__ == "__main__":
    demonstrate_hash_properties()
    demonstrate_integrity_verification()
    demonstrate_collision_resistance()
    demonstrate_merkle_tree_concept()
    
    print("\n" + "="*60)
    print("CONCLUSION: Git's cryptographic hashing provides:")
    print("- Deterministic content addressing")
    print("- Automatic corruption detection") 
    print("- Strong collision resistance")
    print("- Merkle tree integrity propagation")
    print("="*60)