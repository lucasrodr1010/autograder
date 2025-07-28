#!/usr/bin/env python3
"""
Test script for the autograder functionality
This script tests the core autograder logic without the GUI
"""

import subprocess
import sys
import os
from pathlib import Path

def test_base_solution():
    """Test if the base solution (LR) can be executed"""
    print("Testing base solution...")
    
    lr_path = Path("PCA6/LR")
    if not lr_path.exists():
        print("❌ LR folder not found")
        return False
        
    # Find main script
    main_script = None
    for file in lr_path.glob("*.py"):
        if not file.name.startswith("fibonacci_ratio"):
            main_script = file
            break
            
    if not main_script:
        print("❌ Main script not found in LR folder")
        return False
        
    print(f"✅ Found main script: {main_script.name}")
    
    # Test execution
    try:
        result = subprocess.run(
            [sys.executable, str(main_script)],
            input="1, 1\n10\n",
            text=True,
            capture_output=True,
            cwd=str(lr_path),
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Base solution executes successfully")
            print("Sample output:")
            print(result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout)
            return True
        else:
            print(f"❌ Base solution failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing base solution: {e}")
        return False

def test_student_submissions():
    """Test if student submissions can be found and executed"""
    print("\nTesting student submissions...")
    
    pca6_path = Path("PCA6")
    if not pca6_path.exists():
        print("❌ PCA6 folder not found")
        return False
        
    student_folders = []
    for item in pca6_path.iterdir():
        if item.is_dir() and item.name != "LR" and not item.name.startswith("__"):
            python_files = list(item.glob("*.py"))
            if python_files:
                student_folders.append(item)
                
    print(f"✅ Found {len(student_folders)} student submissions")
    
    # Test a few submissions
    test_count = min(3, len(student_folders))
    successful_tests = 0
    
    for i, folder in enumerate(student_folders[:test_count]):
        print(f"Testing {folder.name}...")
        
        # Find main script
        main_script = None
        for file in folder.glob("*.py"):
            if not file.name.startswith("fibonacci_ratio"):
                main_script = file
                break
                
        if not main_script:
            print(f"  ❌ No main script found in {folder.name}")
            continue
            
        # Test execution
        try:
            result = subprocess.run(
                [sys.executable, str(main_script)],
                input="1, 1\n5\n",
                text=True,
                capture_output=True,
                cwd=str(folder),
                timeout=10
            )
            
            if result.returncode == 0:
                print(f"  ✅ {folder.name} executes successfully")
                successful_tests += 1
            else:
                print(f"  ❌ {folder.name} failed: {result.stderr[:100]}...")
                
        except Exception as e:
            print(f"  ❌ Error testing {folder.name}: {e}")
            
    print(f"✅ {successful_tests}/{test_count} test submissions executed successfully")
    return successful_tests > 0

def main():
    """Run all tests"""
    print("=== Autograder Test Suite ===\n")
    
    # Test base solution
    base_ok = test_base_solution()
    
    # Test student submissions
    students_ok = test_student_submissions()
    
    # Summary
    print("\n=== Test Summary ===")
    if base_ok and students_ok:
        print("✅ All tests passed! Autograder should work correctly.")
        print("\nTo run the autograder:")
        print("python autograder.py")
    else:
        print("❌ Some tests failed. Please check the setup.")
        if not base_ok:
            print("- Base solution (LR) needs to be fixed")
        if not students_ok:
            print("- Student submissions have issues")

if __name__ == "__main__":
    main() 