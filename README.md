# COP2273 Autograder

A visual autograder for COP2273 assignments that can automatically test student submissions against a base solution.

## Features

- **Visual Interface**: Easy-to-use GUI built with tkinter
- **Dual Mode Support**:
  - **Folder Mode**: For assignments with multiple student folders (e.g., PCA6)
  - **File Mode**: For assignments with single Python files
- **Utility Import Support**: Import helper modules like graphics.py
- **Custom Test Cases**: Add multiple test cases through the interface
- **Robust Comparison**: Handles formatting differences and runtime errors
- **Real-time Progress**: Shows grading progress and results
- **Color-coded Results**: Visual indicators for pass/fail status
- **Scrollable Test Cases**: Easy management of multiple test cases
- **Automatic Difference Analysis**: Shows output differences for all mismatches
- **Detailed Output Analysis**: Optional detailed debugging with side-by-side comparison
- **Single Submission Testing**: Test individual submissions for debugging
- **Resizable Windows**: Main window and results can be resized for better viewing
- **Results Management**: Clear, save, and open results in separate windows
- **Pull-Out Output**: Drag output into separate windows with real-time updates
- **Drag & Scale**: Resize and move output windows independently
- **Font Scaling**: Zoom in/out with buttons or keyboard shortcuts (Ctrl+/-)
- **Clipboard Support**: Copy results to clipboard for easy sharing

## Requirements

- Python 3.6 or higher
- tkinter (usually included with Python)
- pathlib (usually included with Python)

## Installation

1. Clone or download this repository
2. Install dependencies (if needed):
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Autograder

1. **Start the autograder**:

   ```bash
   python autograder.py
   ```

2. **Select Mode**:

   - **Folder Mode**: For assignments with multiple student folders
   - **File Mode**: For assignments with single Python files

3. **Configure paths**:

   - **Base Solution**: Select the reference solution (file or folder)
   - **Assignment Path**: Select the assignment folder or file to grade
   - **Utility Path** (optional): Select folder containing helper modules (e.g., graphics.py)

4. **Add test cases**:

   - Click "Add Test Case" to add new test cases
   - Each test case should contain the input that will be provided to the programs
   - Enter your test input in the text area (placeholder text will disappear when you start typing)

5. **Run the autograder**:

   - Click "Run Autograder" to start grading
   - The system will:
     - Run the base solution with all test cases
     - Run each student submission with the same test cases
     - Compare outputs and generate scores
     - Display results in real-time

6. **Debugging Options**:

   - **Show Detailed Output Analysis**: Check this to see detailed comparisons when outputs don't match (basic differences are always shown)
   - **Test Single Submission**: Use this to test and debug individual submissions

7. **Results Management**:

   - **Clear Results**: Clear the current results display
   - **Open in New Window**: Open results in a separate, resizable window for better viewing
   - **Pull Out Output**: Create draggable, scalable output windows with real-time updates
   - **Save Results**: Save results to a text file for later review
   - **Copy to Clipboard**: Copy results to clipboard for easy sharing

8. **Output Window Features**:
   - **Drag & Move**: Click and drag window title bar to move
   - **Resize**: Drag window edges to resize
   - **Font Scaling**: Use A+/A- buttons or Ctrl+/- keyboard shortcuts
   - **Real-time Updates**: Output windows automatically update as grading progresses
   - **Keyboard Shortcuts**: Ctrl+S (save), Ctrl+C (copy), Ctrl+/- (zoom)

### Mode Examples

#### Folder Mode (e.g., PCA6)

**Use when each student has their own folder with multiple files**

```
assignments/PCA6/
├── LR/                    # Base solution
│   ├── LR_PCA6.py
│   └── fibonacci_ratio.py
├── AF/                    # Student submission
│   ├── AF_PCA6.py
│   └── fibonacci_ratio.py
└── ...                    # More student folders
```

**Configuration:**

- Mode: Folder
- Base Solution: `assignments/PCA6/LR/`
- Assignment Path: `assignments/PCA6/`
- Utility Path: (leave empty or set to UTILITIES/)

#### File Mode (e.g., single script assignments)

**Use when all Python files are in one folder (self-driving scripts)**

```
Assignment/
├── solution.py            # Base solution
├── student1.py           # Student submission
├── student2.py           # Student submission
└── graphics.py           # Utility module
```

**Configuration:**

- Mode: File
- Base Solution: `Assignment/solution.py`
- Assignment Path: `Assignment/` (folder containing all Python files)
- Utility Path: `Assignment/` (for graphics.py)

### Test Case Format

Test cases should provide input in the format expected by the programs. For example:

**PCA6 Fibonacci Sequence:**

```
1, 1
10
```

**Simple Calculator:**

```
5
+
3
```

**Graphics Assignment:**

```
100
200
circle
```

## Output Interpretation

### Score Indicators

- **✅ Green**: 100% correct (all test cases passed)
- **🟡 Yellow**: 80-99% correct (most test cases passed)
- **❌ Red**: Below 80% correct (significant issues)

### Error Types

- **Runtime errors**: Programs that crash or have syntax errors
- **Output mismatch**: Programs that run but produce incorrect output
- **Timeout**: Programs that take too long to execute (>30 seconds)

### Debugging Output Mismatches

When outputs don't match, the autograder automatically shows:

1. **Basic Difference Analysis** (always shown):

   - Normalized expected vs. actual output
   - Key differences using diff format
   - Clear indication of what was expected vs. what was received

2. **Detailed Analysis** (optional): Check "Show Detailed Output Analysis" to see:

   - Raw base and student outputs
   - Normalized versions for comparison
   - Complete line-by-line differences using diff
   - Input that was provided

3. **Test Single Submission**: Use "Test Single Submission" to:
   - Select a specific student submission
   - Run it against the base solution
   - See detailed analysis for each test case
   - Debug formatting or logic issues

## Customization

### Adding New Test Cases

1. Click "Add Test Case" in the interface
2. Enter the input values in the text area
3. Each line represents one input prompt for the program

### Modifying Comparison Logic

The `compare_outputs()` method in the `AutograderGUI` class handles output comparison. You can modify this to:

- Adjust tolerance for floating-point differences
- Ignore specific formatting differences
- Add custom comparison rules

### Timeout Settings

The execution timeout is set to 30 seconds per test case. You can modify this in the `execute_script()` method.

### Utility Module Support

To use utility modules like graphics.py:

1. Set the "Utility Path" to the folder containing the utility modules
2. The autograder will add this path to the PYTHONPATH environment variable
3. Student submissions can then import these modules normally

## Troubleshooting

### Common Issues

1. **"Base solution failed to run"**:

   - Check that the base solution path contains valid Python files
   - Ensure the main script can be found and executed
   - Verify any required utility modules are accessible

2. **"Student submission failed to run"**:

   - Check for syntax errors in student code
   - Verify that required modules are present
   - Ensure utility paths are correctly configured

3. **"Output mismatch"**:

   - Check if the comparison is too strict
   - Verify that test cases are appropriate for the assignment
   - Consider normalizing output formats

4. **Import errors**:
   - Set the "Utility Path" to include folders with required modules
   - Ensure the utility path is correctly formatted

### Debug Mode

To see more detailed error information, you can modify the code to print additional debugging information in the `run_autograder_thread()` method.

## Extending for Other Assignments

To adapt this autograder for other assignments:

1. **Modify the GUI title** and labels as needed
2. **Update the main script detection** in `find_main_script()` if needed
3. **Adjust test case format** to match the new assignment's input requirements
4. **Modify output comparison** if the new assignment has different output formats
5. **Set utility paths** for any required helper modules

```

```
