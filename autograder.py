import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import os
import sys
import threading
import time
import re
from pathlib import Path
import difflib
import traceback

class AutograderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("COP2273 Autograder")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)  # Make window resizable
        
        # Variables
        self.base_solution_path = tk.StringVar()
        self.assignment_folder_path = tk.StringVar()
        self.mode = tk.StringVar(value="folder")
        self.utility_path = tk.StringVar()
        self.test_cases = []
        self.results = []
        self.is_running = False
        self.show_details = tk.BooleanVar(value=False)
        
        # Setup GUI
        self.setup_gui()

    def setup_gui(self):
        # ── make the entire window vertically scrollable ────────────────
        self.outer_canvas = tk.Canvas(self.root, highlightthickness=0)
        vscroll_total = ttk.Scrollbar(self.root, orient="vertical", command=self.outer_canvas.yview)
        self.outer_canvas.configure(yscrollcommand=vscroll_total.set)

        self.outer_canvas.pack(side="left",  fill="both", expand=True)
        vscroll_total.pack(side="right", fill="y")

        # all existing widgets will live inside this frame
        main_frame = ttk.Frame(self.outer_canvas, padding="10")
        window_id  = self.outer_canvas.create_window((0, 0), window=main_frame, anchor="nw")

        # keep scroll region and inner‑frame width in sync
        def _resize(event):
            self.outer_canvas.configure(
                scrollregion=self.outer_canvas.bbox("all"))
            self.outer_canvas.itemconfigure(window_id, width=self.outer_canvas.winfo_width())

        def _stretch_inner(event):
            # keep inner frame exactly as wide as the canvas viewport
            self.outer_canvas.itemconfigure(window_id, width=event.width)

        main_frame.bind("<Configure>", _resize)
        self.outer_canvas.bind("<Configure>", _stretch_inner)

        # (from here onwards the original body of setup_gui() begins …)
        # ----------------------------------------------------------------
        # Title
        title_label = ttk.Label(main_frame, text="COP2273 Autograder",
                                font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # make columns grow with the window
        # 1️⃣  Let column 1 do the stretching, keep cols 0 & 2 compact
        main_frame.columnconfigure(0, weight=0)   # labels
        main_frame.columnconfigure(1, weight=1)              # big widgets
        main_frame.columnconfigure(2, weight=0)   # buttons

        # 2️⃣  Remove hard‑coded character widths so the widgets may expand
        

        # Mode Selection
        mode_frame = ttk.LabelFrame(main_frame, text="Mode Selection", padding="10")
        mode_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Radiobutton(mode_frame, text="Folder Mode", variable=self.mode, value="folder", 
                       command=self.on_mode_change).grid(row=0, column=0, padx=(0, 20))
        ttk.Radiobutton(mode_frame, text="File Mode", variable=self.mode, value="file", 
                       command=self.on_mode_change).grid(row=0, column=1)
        
        # Path Selection Section
        path_frame = ttk.LabelFrame(main_frame, text="Path Configuration", padding="10")
        path_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        path_frame.columnconfigure(1, weight=1)
        
        # Base Solution
        ttk.Label(path_frame, text="Base Solution:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.base_entry = ttk.Entry(path_frame, textvariable=self.base_solution_path)
        self.base_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        self.base_button = ttk.Button(path_frame, text="Browse", command=self.browse_base_solution)
        self.base_button.grid(row=0, column=2, pady=5)
        
        # Assignment Folder/File
        ttk.Label(path_frame, text="Assignment Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.assignment_entry = ttk.Entry(path_frame, textvariable=self.assignment_folder_path)
        self.assignment_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        self.assignment_button = ttk.Button(path_frame, text="Browse", command=self.browse_assignment_path)
        self.assignment_button.grid(row=1, column=2, pady=5)
        
        # Utility Path (optional)
        ttk.Label(path_frame, text="Utility Path (optional):").grid(row=2, column=0, sticky=tk.W, pady=5)
        utility_entry = ttk.Entry(path_frame, textvariable=self.utility_path)
        utility_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5), pady=5)
        ttk.Button(path_frame, text="Browse", command=self.browse_utility_path).grid(row=2, column=2, pady=5)
        
        # Test Cases Section
        test_frame = ttk.LabelFrame(main_frame, text="Test Cases", padding="10")
        test_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        test_frame.columnconfigure(0, weight=1)
        test_frame.rowconfigure(1, weight=1)
        
        # Test case controls
        test_controls = ttk.Frame(test_frame)
        test_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(test_controls, text="Add Test Case", command=self.add_test_case).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(test_controls, text="Clear All", command=self.clear_test_cases).pack(side=tk.LEFT)
        
        style  = ttk.Style(self.root)
        default_bg = style.lookup("TFrame", "background") or style.lookup(".", "background")

        # ─── Test cases scrollable frame ──────────────────────────────
        self.test_canvas = tk.Canvas(
        test_frame,
        highlightthickness=0,
        bg=default_bg     
        )

        vscroll = ttk.Scrollbar(test_frame, orient="vertical",
                                command=self.test_canvas.yview)
        self.test_canvas.configure(yscrollcommand=vscroll.set)

        # geometry
        self.test_canvas.grid(row=1, column=0, sticky="nsew")
        vscroll.grid(row=1, column=1, sticky="ns")

        # inner frame that will hold the individual test‑case widgets
        self.test_cases_frame = ttk.Frame(self.test_canvas, style="CanvasHost.TFrame")
        style.configure("CanvasHost.TFrame", background=default_bg)
        inner_window = self.test_canvas.create_window(
            (0, 0), window=self.test_cases_frame, anchor="nw")

        # let the canvas know its size whenever the inner frame changes
        def _on_frame_config(event):
            self.test_canvas.configure(scrollregion=self.test_canvas.bbox("all"))
            # stretch the inner window to the full canvas width
            self.test_canvas.itemconfigure(inner_window, width=event.width)

        self.test_cases_frame.bind("<Configure>", _on_frame_config)
        
        # Add default test case
        self.add_test_case()



       

       
        # Options Section
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Checkbutton(options_frame, text="Show Detailed Output Analysis", 
                       variable=self.show_details).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(options_frame, text="Test Single Submission", 
                  command=self.test_single_submission).pack(side=tk.LEFT)
        
        # Control Buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        self.run_button = ttk.Button(control_frame, text="Run Autograder", command=self.run_autograder)
        self.run_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_autograder, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)
        
        # Progress
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(control_frame, textvariable=self.progress_var).pack(side=tk.LEFT, padx=(20, 0))
        
        # Results Section
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        
        # Results controls
        results_controls_frame = ttk.Frame(results_frame)
        results_controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        ttk.Button(results_controls_frame, text="Clear Results", command=self.clear_results).pack(side="left", padx=(0, 10))
        ttk.Button(results_controls_frame, text="Open in New Window", command=self.open_results_window).pack(side="left", padx=(0, 10))
        ttk.Button(results_controls_frame, text="Save Results", command=self.save_results).pack(side="left")
        
        # Results text area
        self.results_text = scrolledtext.ScrolledText(
        results_frame, height=15, font=("Consolas", 10),
        )
        self.results_text.configure(bg=default_bg, fg="black", insertbackground="black")
        self.results_text.grid(row=1, column=0, sticky="nsew")
        
        
        # Configure main frame weights
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 5))
        
        self.status_var = tk.StringVar(value="Ready to grade")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief="sunken", anchor="w")
        status_label.pack(fill="x")

        self._setup_scrolling()

    def _setup_scrolling(self):
        """
        Binds the mouse wheel event to the entire application and intelligently
        scrolls the correct canvas. It avoids interfering with self-scrolling
        widgets like Text and ScrolledText.
        """
        def _on_global_scroll(event):
            # Find the widget directly under the mouse pointer
            widget_under_pointer = self.root.winfo_containing(event.x_root, event.y_root)
            
            if widget_under_pointer is None:
                return # Not over any of our widgets

            # Check if the widget is a type that should scroll itself.
            # We walk up the widget hierarchy from the widget under the pointer.
            w = widget_under_pointer
            while w:
                if isinstance(w, (tk.Text, tk.Listbox)):
                    # This widget has its own scrollbar, so let it handle the event.
                    return
                # Stop if we reach the top-level window
                if w == self.root:
                    break
                try:
                    w = w.master
                except Exception:
                    break # Should not happen, but a safeguard

            # If we got here, we're not over a self-scrolling widget.
            # Now, decide which of our two main canvases to scroll.
            try:
                # Get the screen coordinates of the inner 'test_canvas'
                x, y, width, height = self.test_canvas.winfo_rootx(), self.test_canvas.winfo_rooty(), self.test_canvas.winfo_width(), self.test_canvas.winfo_height()
                # Check if the mouse pointer is inside the bounds of the 'test_canvas'
                if x <= event.x_root < x + width and y <= event.y_root < y + height:
                    canvas_to_scroll = self.test_canvas
                else:
                    # If not, it must be over the main 'outer_canvas'
                    canvas_to_scroll = self.outer_canvas
            except tk.TclError:
                # Fallback in case a widget was destroyed during the event
                canvas_to_scroll = self.outer_canvas

            # Perform the scroll action on the identified canvas
            if sys.platform == "darwin":  # macOS
                canvas_to_scroll.yview_scroll(-1 * event.delta, "units")
            else:  # Windows/Linux
                canvas_to_scroll.yview_scroll(-1 * int(event.delta / 120), "units")

        # Bind the master scroll function to the entire application
        self.root.bind_all("<MouseWheel>", _on_global_scroll)
        # Extra bindings for Linux scroll buttons
        self.root.bind_all("<Button-4>", lambda e: self.outer_canvas.yview_scroll(-1, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.outer_canvas.yview_scroll(1, "units"))


    def on_mode_change(self):
        """Handle mode change between file and folder"""
        mode = self.mode.get()
        if mode == "file":
            self.base_entry.config(state="normal")
            self.assignment_entry.config(state="normal")
        else:
            self.base_entry.config(state="normal")
            self.assignment_entry.config(state="normal")
        
    def browse_base_solution(self):
        mode = self.mode.get()
        if mode == "file":
            path = filedialog.askopenfilename(title="Select Base Solution File", filetypes=[("Python files", "*.py")])
        else:
            path = filedialog.askdirectory(title="Select Base Solution Folder")
        if path:
            self.base_solution_path.set(path)
            
    def browse_assignment_path(self):
        mode = self.mode.get()
        if mode == "file":
            path = filedialog.askdirectory(title="Select Assignment Folder (contains Python files)")
        else:
            path = filedialog.askdirectory(title="Select Assignment Folder")
        if path:
            self.assignment_folder_path.set(path)
            
    def browse_utility_path(self):
        path = filedialog.askdirectory(title="Select Utility Folder (e.g., graphics.py)")
        if path:
            self.utility_path.set(path)
            
    def add_test_case(self):
        test_case = TestCaseFrame(self.test_cases_frame, len(self.test_cases), self)
        test_case.grid(row=len(self.test_cases), column=0, sticky=(tk.W, tk.E), pady=2)
        self.test_cases.append(test_case)
        
    def clear_test_cases(self):
        # Destroy all test case widgets
        for test_case in self.test_cases:
            try:
                if test_case.winfo_exists():
                    test_case.destroy()
            except tk.TclError:
                # Widget already destroyed, skip it
                pass
        self.test_cases.clear()
        self.add_test_case()
        
    def get_test_cases(self):
        cases = []
        # Clean up destroyed widgets from the list
        self.test_cases = [tc for tc in self.test_cases if tc.winfo_exists()]
        
        # Get valid test cases
        for test_case in self.test_cases:
            try:
                if test_case.is_valid():
                    cases.append(test_case.get_data())
            except tk.TclError:
                # Widget was destroyed, skip it
                continue
        return cases
        
    def run_autograder(self):
        if not self.base_solution_path.get() or not self.assignment_folder_path.get():
            messagebox.showerror("Error", "Please select both base solution and assignment paths.")
            return
            
        if not self.get_test_cases():
            messagebox.showerror("Error", "Please add at least one valid test case.")
            return
            
        self.is_running = True
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.status_var.set("Starting autograder...")
        
        # Run in separate thread
        thread = threading.Thread(target=self.run_autograder_thread)
        thread.daemon = True
        thread.start()
        
    def stop_autograder(self):
        self.is_running = False
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set("Stopped")
        self.status_var.set("Autograder stopped")
        
    def run_autograder_thread(self):
        try:
            self.progress_var.set("Starting autograder...")
            
            # Get test cases
            test_cases = self.get_test_cases()
            
            # Find all student submissions
            student_files = self.find_student_submissions()
            
            # Run base solution first
            self.progress_var.set("Running base solution...")
            base_results = self.run_solution(self.base_solution_path.get(), test_cases, "Base Solution")
            
            if not base_results:
                self.update_results("ERROR: Base solution failed to run properly.\n")
                return
                
            # Run student submissions
            total_students = len(student_files)
            for i, student_path in enumerate(student_files):
                if not self.is_running:
                    break
                    
                student_name = os.path.basename(student_path)
                self.progress_var.set(f"Grading {student_name} ({i+1}/{total_students})...")
                
                student_results = self.run_solution(student_path, test_cases, student_name)
                self.compare_results(base_results, student_results, student_name)
                
            self.progress_var.set("Completed")
            self.status_var.set("Grading completed successfully")
            self.update_results("\n=== AUTOMATIC GRADING COMPLETED ===\n")
            
        except Exception as e:
            self.update_results(f"ERROR: {str(e)}\n{traceback.format_exc()}")
            self.status_var.set("Error occurred during grading")
        finally:
            self.is_running = False
            self.run_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            
    def find_student_submissions(self):
        """Find all student submission folders or files"""
        student_paths = []
        assignment_path = Path(self.assignment_folder_path.get())
        
        if self.mode.get() == "file":
            # File mode - find all Python files in the folder
            for item in assignment_path.iterdir():
                if item.is_file() and item.suffix == '.py':
                    student_paths.append(str(item))
        else:
            # Folder mode - find all subfolders containing Python files
            for item in assignment_path.iterdir():
                if item.is_dir() and not item.name.startswith("__"):
                    # Check if folder contains Python files
                    python_files = list(item.glob("*.py"))
                    if python_files:
                        student_paths.append(str(item))
                    
        return student_paths
        
    def run_solution(self, path, test_cases, name):
        """Run a solution with all test cases"""
        results = []
        
        # Find main script
        if self.mode.get() == "file":
            # In file mode, the path is already the Python file
            main_script = path
        else:
            # In folder mode, find the main script in the folder
            main_script = self.find_main_script(path)
            
        if not main_script:
            return None
            
        for i, test_case in enumerate(test_cases):
            try:
                output = self.execute_script(main_script, test_case["input"], path)
                results.append({
                    "test_case": i + 1,
                    "input": test_case["input"],
                    "output": output,
                    "error": None
                })
            except Exception as e:
                results.append({
                    "test_case": i + 1,
                    "input": test_case["input"],
                    "output": None,
                    "error": str(e)
                })
                
        return results
        
    def find_main_script(self, folder_path):
        """Find the main Python script in a folder"""
        folder = Path(folder_path)
        
        # Look for Python files
        python_files = list(folder.glob("*.py"))
        if not python_files:
            return None
            
        # Prefer files that don't look like modules
        for file in python_files:
            if not file.name.startswith("fibonacci_ratio") and not file.name.startswith("graphics"):
                return str(file)
                
        # If no main script found, return first Python file
        return str(python_files[0]) if python_files else None
        
    def execute_script(self, script_path, input_data, working_dir):
        """Execute a Python script with given input"""
        try:
            # Prepare input
            input_text = "\n".join(input_data) + "\n"
            
            # Set up environment with utility path if provided
            env = os.environ.copy()
            if self.utility_path.get():
                # Add utility path to Python path
                python_path = env.get('PYTHONPATH', '')
                if python_path:
                    python_path += os.pathsep + self.utility_path.get()
                else:
                    python_path = self.utility_path.get()
                env['PYTHONPATH'] = python_path
            
            if self.mode.get() == "file":
                # In file mode, run the script directly from its directory
                script_dir = os.path.dirname(script_path)
                script_filename = os.path.basename(script_path)
                
                # Run the script
                result = subprocess.run(
                    [sys.executable, script_filename],
                    input=input_text,
                    text=True,
                    capture_output=True,
                    cwd=script_dir,
                    env=env,
                    timeout=30  # 30 second timeout
                )
            else:
                # In folder mode, use the working directory approach
                script_filename = os.path.basename(script_path)
                
                # Run the script
                result = subprocess.run(
                    [sys.executable, script_filename],
                    input=input_text,
                    text=True,
                    capture_output=True,
                    cwd=working_dir,
                    env=env,
                    timeout=30  # 30 second timeout
                )
            
            if result.returncode != 0:
                raise Exception(f"Runtime error: {result.stderr}")
                
            return result.stdout
            
        except subprocess.TimeoutExpired:
            raise Exception("Execution timeout (30 seconds)")
        except Exception as e:
            raise Exception(f"Execution error: {str(e)}")
            
    def compare_results(self, base_results, student_results, student_name):
        """Compare student results with base results"""
        if not student_results:
            self.update_results(f"❌ {student_name}: FAILED TO RUN\n")
            return
            
        total_tests = len(base_results)
        passed_tests = 0
        errors = []
        
        for i, (base_result, student_result) in enumerate(zip(base_results, student_results)):
            if student_result["error"]:
                errors.append(f"Test {i+1}: Runtime error - {student_result['error']}")
                continue
                
            # Compare outputs
            if self.compare_outputs(base_result["output"], student_result["output"]):
                passed_tests += 1
            else:
                errors.append(f"Test {i+1}: Output mismatch")
                
                # Always show basic difference analysis for output mismatches
                self.show_basic_difference_analysis(base_result, student_result, student_name, i+1)
                
                # Show detailed analysis if enabled
                if self.show_details.get():
                    self.show_output_analysis(base_result, student_result, student_name, i+1)
                
        # Calculate score
        score = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Display results
        if score == 100:
            self.update_results(f"✅ {student_name}: {score:.1f}% ({passed_tests}/{total_tests})\n")
        elif score >= 80:
            self.update_results(f"🟡 {student_name}: {score:.1f}% ({passed_tests}/{total_tests})\n")
        else:
            self.update_results(f"❌ {student_name}: {score:.1f}% ({passed_tests}/{total_tests})\n")
            
        # Show errors if any
        if errors:
            for error in errors:
                self.update_results(f"    {error}\n")
                
    def show_output_analysis(self, base_result, student_result, student_name, test_num):
        """Show detailed output analysis for debugging"""
        self.update_results(f"\n--- DETAILED ANALYSIS: {student_name} - Test {test_num} ---\n")
        
        # Show input
        self.update_results(f"Input: {' | '.join(base_result['input'])}\n")
        
        # Show base output
        self.update_results(f"Base Output:\n{base_result['output']}\n")
        
        # Show student output
        self.update_results(f"Student Output:\n{student_result['output']}\n")
        
        # Show normalized comparison
        norm_base = self.normalize_output(base_result['output'])
        norm_student = self.normalize_output(student_result['output'])
        
        self.update_results(f"Normalized Base: {norm_base}\n")
        self.update_results(f"Normalized Student: {norm_student}\n")
        
        # Show differences
        if norm_base != norm_student:
            self.update_results("Differences:\n")
            diff = difflib.unified_diff(
                norm_base, norm_student,
                fromfile='Base', tofile='Student',
                lineterm=''
            )
            for line in diff:
                self.update_results(f"  {line}\n")
        
        self.update_results("--- END ANALYSIS ---\n")
                
    def show_basic_difference_analysis(self, base_result, student_result, student_name, test_num):
        """Show basic difference analysis for output mismatches"""
        self.update_results(f"\n--- OUTPUT DIFFERENCES: {student_name} - Test {test_num} ---\n")
        
        # Show normalized comparison
        norm_base = self.normalize_output(base_result['output'])
        norm_student = self.normalize_output(student_result['output'])
        
        self.update_results(f"Expected: {norm_base}\n")
        self.update_results(f"Got:      {norm_student}\n")
        
        # Show key differences
        if norm_base != norm_student:
            self.update_results("Key Differences:\n")
            diff = difflib.unified_diff(
                norm_base, norm_student,
                fromfile='Expected', tofile='Got',
                lineterm=''
            )
            for line in diff:
                if line.startswith('+') or line.startswith('-') or line.startswith('@'):
                    self.update_results(f"  {line}\n")
        
        self.update_results("--- END DIFFERENCES ---\n")
                
    def compare_outputs(self, output1, output2):
        """Compare two outputs, accounting for formatting differences"""
        if not output1 or not output2:
            return False
            
        # Normalize outputs
        norm1 = self.normalize_output(output1)
        norm2 = self.normalize_output(output2)
        
        # Compare normalized outputs
        return norm1 == norm2
        
    def normalize_output(self, output):
        """Normalize output for comparison"""
        if not output:
            return []
            
        # Remove extra whitespace and normalize line endings
        lines = output.strip().split('\n')
        normalized = []
        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                # Remove extra spaces
                line = ' '.join(line.split())
                normalized.append(line)
        return normalized
        
    def test_single_submission(self):
        """Test a single submission for debugging"""
        if not self.base_solution_path.get() or not self.assignment_folder_path.get():
            messagebox.showerror("Error", "Please select both base solution and assignment paths.")
            return
            
        if not self.get_test_cases():
            messagebox.showerror("Error", "Please add at least one valid test case.")
            return
            
        # Get list of student submissions
        student_files = self.find_student_submissions()
        if not student_files:
            messagebox.showerror("Error", "No student submissions found.")
            return
            
        # Create a simple dialog to select submission
        submission_path = self.select_submission_dialog(student_files)
        if not submission_path:
            return
        
        # Run the test
        self.results_text.delete(1.0, tk.END)
        self.update_results(f"Testing single submission: {os.path.basename(submission_path)}\n")
        
        test_cases = self.get_test_cases()
        
        # Run base solution
        self.update_results("Running base solution...\n")
        base_results = self.run_solution(self.base_solution_path.get(), test_cases, "Base Solution")
        
        if not base_results:
            self.update_results("ERROR: Base solution failed to run properly.\n")
            return
            
        # Run student submission
        self.update_results("Running student submission...\n")
        student_results = self.run_solution(submission_path, test_cases, os.path.basename(submission_path))
        
        if not student_results:
            self.update_results("ERROR: Student submission failed to run.\n")
            return
            
        # Show detailed comparison
        self.update_results("\n=== DETAILED COMPARISON ===\n")
        for i, (base_result, student_result) in enumerate(zip(base_results, student_results)):
            self.update_results(f"\n--- Test Case {i+1} ---\n")
            
            # Always show basic differences
            self.show_basic_difference_analysis(base_result, student_result, os.path.basename(submission_path), i+1)
            
            # Show full analysis if detailed mode is enabled
            if self.show_details.get():
                self.show_output_analysis(base_result, student_result, os.path.basename(submission_path), i+1)
        
    def select_submission_dialog(self, student_files):
        """Simple dialog to select a submission"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Submission")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        ttk.Label(dialog, text="Select a submission to test:").pack(pady=10)
        
        # Listbox for submissions
        listbox = tk.Listbox(dialog, height=10)
        listbox.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Populate listbox
        for file_path in student_files:
            listbox.insert(tk.END, os.path.basename(file_path))
        
        selected_path = [None]  # Use list to store result
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected_path[0] = student_files[index]
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Select", command=on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return selected_path[0]
        
    def update_results(self, text):
        """Update the results text area (thread-safe)"""
        self.root.after(0, lambda: self.results_text.insert(tk.END, text))
        self.root.after(0, lambda: self.results_text.see(tk.END))
        
    def clear_results(self):
        """Clear the results text area"""
        self.results_text.delete(1.0, tk.END)
        
    def open_results_window(self):
        """Open results in a new resizable window"""
        results_window = tk.Toplevel(self.root)
        results_window.title("Autograder Results - Detailed View")
        results_window.geometry("1000x700")
        results_window.resizable(True, True)

        window_frame = ttk.Frame(results_window)
        window_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        controls_frame = ttk.Frame(window_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        text_frame = ttk.Frame(window_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        results_window_text = tk.Text(text_frame, wrap="none", font=("Consolas", 10)) # Use 'none' for wrap to make horizontal scrollbar useful
        v_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=results_window_text.yview)
        h_scrollbar = ttk.Scrollbar(text_frame, orient="horizontal", command=results_window_text.xview)
        results_window_text.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Corrected button commands to refer to results_window_text
        ttk.Button(controls_frame, text="Clear", command=lambda: results_window_text.delete(1.0, tk.END)).pack(side="left", padx=(0, 10))
        ttk.Button(controls_frame, text="Save", command=lambda: self.save_text_to_file(results_window_text.get(1.0, tk.END))).pack(side="left", padx=(0, 10))
        ttk.Button(controls_frame, text="Copy All", command=lambda: self.copy_to_clipboard(results_window_text.get(1.0, tk.END))).pack(side="left")

        results_window_text.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        # Corrected variable to get text from the main window's results text widget
        current_results = self.results_text.get(1.0, tk.END)
        results_window_text.insert(1.0, current_results)

        results_window.focus_set()
        
    def save_results(self):
        """Save results to a file"""
        content = self.results_text.get(1.0, tk.END)
        self.save_text_to_file(content)
        
    def save_text_to_file(self, content):
        """Save text content to a file"""
        filename = filedialog.asksaveasfilename(
            title="Save Results",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Results saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {str(e)}")
                
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Success", "Text copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard: {str(e)}")
            



class TestCaseFrame(ttk.Frame):
    def __init__(self, parent, index, autograder_gui):
        super().__init__(parent)
        self.index = index
        self.autograder_gui = autograder_gui
        
        # Input lines
        ttk.Label(self, text=f"Test Case {index + 1}:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        style = ttk.Style(self.autograder_gui.root)
        default_bg   = style.lookup("TFrame", "background") or style.lookup(".", "background")
        # Input text area
        self.input_text = tk.Text(self, height=3, width=50)
        self.input_text.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.input_text.configure(bg=default_bg, fg="black", insertbackground="black")
        
        # Remove button
        ttk.Button(self, text="Remove", command=self.remove).grid(row=0, column=2, padx=(5, 0))
        
        # Configure grid
        self.columnconfigure(1, weight=1)
        
        # Add placeholder text
        self.input_text.insert(tk.END, "Enter test input here...")
        self.input_text.bind("<FocusIn>", self.on_focus_in)
        self.input_text.bind("<FocusOut>", self.on_focus_out)
        self.placeholder_text = "Enter test input here..."
        self.has_content = False
        
        
    def on_focus_in(self, event):
        """Handle focus in event"""
        if not self.has_content:
            self.input_text.delete(1.0, tk.END)
            self.input_text.config(fg="black")
            
    def on_focus_out(self, event):
        """Handle focus out event"""
        if not self.input_text.get(1.0, tk.END).strip():
            self.input_text.insert(tk.END, self.placeholder_text)
            self.input_text.config(fg="gray")
            self.has_content = False
        else:
            self.has_content = True
        
    def is_valid(self):
        """Check if test case is valid"""
        content = self.input_text.get(1.0, tk.END).strip()
        return bool(content) and content != self.placeholder_text
        
    def get_data(self):
        """Get test case data"""
        input_text = self.input_text.get(1.0, tk.END).strip()
        if input_text == self.placeholder_text:
            return {"input": []}
        return {
            "input": input_text.split('\n') if input_text else []
        }
        
    def remove(self):
        """Remove this test case"""
        try:
            # Remove from autograder's test_cases list
            if self in self.autograder_gui.test_cases:
                self.autograder_gui.test_cases.remove(self)
            self.destroy()
        except tk.TclError:
            # Widget already destroyed
            pass

def main():
    root = tk.Tk()
    if sys.platform == "darwin":                       
        root.tk.call("ttk::style", "theme", "use", "clam")  # force light (clam) theme on Mac
    app = AutograderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main() 