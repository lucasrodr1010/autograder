#!/usr/bin/env python3
"""
Simple test script to verify autograder core functionality
"""

import subprocess
import sys
import os
from pathlib import Path

def test_pca6_execution():
    """Test PCA6 execution with sample input"""
    print("Testing PCA6 execution...")
    
    # Test LR solution
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
    
    # Test execution with sample input
    try:
        # Use a simple test case - provide input exactly as expected
        test_input = "1, 1\n5\n"
        
        # Change to the LR directory and run the script
        script_filename = os.path.basename(main_script)
        result = subprocess.run(
            [sys.executable, script_filename],
            input=test_input,
            text=True,
            capture_output=True,
            cwd=str(lr_path),
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ LR solution executes successfully")
            print("Sample output:")
            print(result.stdout)
            return True
        else:
            print(f"❌ LR solution failed: {result.stderr}")
            print(f"Return code: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ LR solution timed out")
        return False
    except Exception as e:
        print(f"❌ Error testing LR solution: {e}")
        return False

def test_student_submission():
    """Test a student submission"""
    print("\nTesting student submission...")
    
    # Test AF submission
    af_path = Path("PCA6/AF")
    if not af_path.exists():
        print("❌ AF folder not found")
        return False
        
    # Find main script
    main_script = None
    for file in af_path.glob("*.py"):
        if not file.name.startswith("fibonacci_ratio"):
            main_script = file
            break
            
    if not main_script:
        print("❌ Main script not found in AF folder")
        return False
        
    print(f"✅ Found main script: {main_script.name}")
    
    # Test execution
    try:
        test_input = "1, 1\n5\n"
        
        script_filename = os.path.basename(main_script)
        result = subprocess.run(
            [sys.executable, script_filename],
            input=test_input,
            text=True,
            capture_output=True,
            cwd=str(af_path),
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ AF submission executes successfully")
            print("Sample output:")
            print(result.stdout)
            return True
        else:
            print(f"❌ AF submission failed: {result.stderr}")
            print(f"Return code: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ AF submission timed out")
        return False
    except Exception as e:
        print(f"❌ Error testing AF submission: {e}")
        return False

def test_simple_execution():
    """Test simple Python execution"""
    print("Testing simple Python execution...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", "print('Hello, World!')"],
            text=True,
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0 and "Hello, World!" in result.stdout:
            print("✅ Python execution works")
            return True
        else:
            print(f"❌ Python execution failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Python execution: {e}")
        return False

def test_manual_execution():
    """Test manual execution in LR directory"""
    print("\nTesting manual execution...")
    
    try:
        # Change to LR directory
        os.chdir("PCA6/LR")
        
        # Test with echo command to simulate input
        test_input = "1, 1\n5\n"
        
        result = subprocess.run(
            [sys.executable, "LR_PCA6.py"],
            input=test_input,
            text=True,
            capture_output=True,
            timeout=10
        )
        
        # Change back to original directory
        os.chdir("../..")
        
        if result.returncode == 0:
            print("✅ Manual execution works")
            print("Output:")
            print(result.stdout)
            return True
        else:
            print(f"❌ Manual execution failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error in manual execution: {e}")
        # Change back to original directory
        try:
            os.chdir("../..")
        except:
            pass
        return False

def main():
    """Run tests"""
    print("=== Core Functionality Test ===\n")
    
    # Test basic Python execution first
    python_ok = test_simple_execution()
    
    if not python_ok:
        print("❌ Basic Python execution failed. Cannot proceed.")
        return
    
    # Test manual execution
    manual_ok = test_manual_execution()
    
    # Test LR solution
    lr_ok = test_pca6_execution()
    
    # Test student submission
    student_ok = test_student_submission()
    
    # Summary
    print("\n=== Test Summary ===")
    if lr_ok and student_ok:
        print("✅ Core functionality works! Autograder should be able to grade PCA6.")
        print("\nTo run the autograder:")
        print("python autograder.py")
        print("\nConfiguration for PCA6:")
        print("- Mode: Folder")
        print("- Base Solution: PCA6/LR/")
        print("- Assignment Path: PCA6/")
        print("- Test Case: 1, 1\\n5")
    else:
        print("❌ Some tests failed. Please check the setup.")
        if not lr_ok:
            print("- LR solution needs to be fixed")
        if not student_ok:
            print("- Student submissions have issues")

if __name__ == "__main__":
    main() 