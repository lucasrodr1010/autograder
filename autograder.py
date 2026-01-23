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
from PIL import Image, ImageTk


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

class UIConfig:
    """Configuration constants for the autograder UI"""
    # Window settings
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    TITLE = "COP2273 Autograder"
    
    # Font settings
    TITLE_FONT = ("Arial", 16, "bold")
    MONO_FONT = ("Consolas", 10)
    
    # Test execution
    EXECUTION_TIMEOUT = 30  # seconds
    
    # Widget dimensions
    TEST_CASE_HEIGHT = 3
    TEST_CASE_WIDTH = 50
    RESULTS_HEIGHT = 15
    
    # Spacing
    STANDARD_PADDING = 10
    SECTION_PADDING_Y = (0, 10)
    TITLE_PADDING_Y = (0, 20)
    BUTTON_PADDING_X = (0, 5)
    
    # Results window
    RESULTS_WINDOW_WIDTH = 1000
    RESULTS_WINDOW_HEIGHT = 700

    # Tokyo Night Color Palette
    BG_COLOR = "#1a1b26"        # Main background (Deep Blue/Black)
    FG_COLOR = "#c0caf5"        # Main foreground text (Soft White)
    PANEL_BG = "#24283b"        # Slightly lighter background for panels
    ACCENT_COLOR = "#7aa2f7"    # Bright blue accent
    BUTTON_BG = "#33467c"       # Button background
    BUTTON_FG = "#c0caf5"       # Button text
    BUTTON_HOVER = "#414868"    # Button hover color
    ENTRY_BG = "#16161e"        # Input field background (Darker)
    ENTRY_FG = "#c0caf5"        # Input field text
    BORDER_COLOR = "#414868"    # Border color
    SUCCESS_COLOR = "#9ece6a"   # Green for success
    ERROR_COLOR = "#f7768e"     # Red for errors
    WARNING_COLOR = "#e0af68"   # Yellow/Orange for warnings
    SELECTION_BG = "#33467c"    # Text selection background
    
    # Assets
    ICON_PATH = "icon.png"


# ============================================================================
# MAIN AUTOGRADER GUI CLASS
# ============================================================================

class AutograderGUI:
    def __init__(self, root):
        """Initialize the autograder GUI.
        
        Args:
            root: The Tkinter root window
        """
        self.root = root
        self.root.title(UIConfig.TITLE)
        self.root.geometry(f"{UIConfig.WINDOW_WIDTH}x{UIConfig.WINDOW_HEIGHT}")
        self.root.resizable(True, True)
        
        # Set application icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), UIConfig.ICON_PATH)
            if os.path.exists(icon_path):
                icon_image = Image.open(icon_path)
                self.icon_photo = ImageTk.PhotoImage(icon_image)
                self.root.iconphoto(True, self.icon_photo)
        except Exception as e:
            print(f"Failed to load icon: {e}")
        
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
        """Set up the main GUI layout and all widgets."""
        # Configure styles first
        self._configure_styles()
        
        # Setup scrollable container
        self.outer_canvas = tk.Canvas(self.root, highlightthickness=0, bg=UIConfig.BG_COLOR)
        vertical_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.outer_canvas.yview)
        self.outer_canvas.configure(yscrollcommand=vertical_scrollbar.set)

        self.outer_canvas.pack(side="left", fill="both", expand=True)
        vertical_scrollbar.pack(side="right", fill="y")

        # Main frame for all widgets
        main_frame = ttk.Frame(self.outer_canvas, padding=str(UIConfig.STANDARD_PADDING))
        scroll_window_id = self.outer_canvas.create_window((0, 0), window=main_frame, anchor="nw")

        # Keep scroll region and inner frame width in sync
        def _resize(event):
            self.outer_canvas.configure(scrollregion=self.outer_canvas.bbox("all"))
            self.outer_canvas.itemconfigure(scroll_window_id, width=self.outer_canvas.winfo_width())

        def _stretch_inner(event):
            self.outer_canvas.itemconfigure(scroll_window_id, width=event.width)

        main_frame.bind("<Configure>", _resize)
        self.outer_canvas.bind("<Configure>", _stretch_inner)

        # Custom style for Title to match background
        title_label = ttk.Label(main_frame, text=UIConfig.TITLE, font=UIConfig.TITLE_FONT, foreground=UIConfig.ACCENT_COLOR)
        title_label.grid(row=0, column=0, columnspan=3, pady=UIConfig.TITLE_PADDING_Y)

        # Configure column weights for responsive layout
        main_frame.columnconfigure(0, weight=0)  # Labels
        main_frame.columnconfigure(1, weight=1)  # Main content (expandable)
        main_frame.columnconfigure(2, weight=0)  # Buttons

        # Mode Selection
        mode_frame = ttk.LabelFrame(main_frame, text="Mode Selection", padding=str(UIConfig.STANDARD_PADDING))
        mode_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=UIConfig.SECTION_PADDING_Y)
        
        ttk.Radiobutton(mode_frame, text="Folder Mode", variable=self.mode, value="folder", 
                       command=self.on_mode_change).grid(row=0, column=0, padx=(0, 20))
        ttk.Radiobutton(mode_frame, text="File Mode", variable=self.mode, value="file", 
                       command=self.on_mode_change).grid(row=0, column=1)
        
        # Path Selection Section
        path_frame = ttk.LabelFrame(main_frame, text="Path Configuration", padding=str(UIConfig.STANDARD_PADDING))
        path_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=UIConfig.SECTION_PADDING_Y)
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
        test_frame = ttk.LabelFrame(main_frame, text="Test Cases", padding=str(UIConfig.STANDARD_PADDING))
        test_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=UIConfig.SECTION_PADDING_Y)
        test_frame.columnconfigure(0, weight=1)
        test_frame.rowconfigure(1, weight=1)
        
        # Test case controls
        test_controls = ttk.Frame(test_frame)
        test_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(test_controls, text="Add Test Case", command=self.add_test_case).pack(side=tk.LEFT, padx=UIConfig.BUTTON_PADDING_X)
        ttk.Button(test_controls, text="Clear All", command=self.clear_test_cases).pack(side=tk.LEFT)

        # Test cases scrollable frame
        self.test_canvas = tk.Canvas(test_frame, highlightthickness=0, bg=UIConfig.BG_COLOR)
        vertical_scrollbar = ttk.Scrollbar(test_frame, orient="vertical", command=self.test_canvas.yview)
        self.test_canvas.configure(yscrollcommand=vertical_scrollbar.set)

        # Geometry
        self.test_canvas.grid(row=1, column=0, sticky="nsew")
        vertical_scrollbar.grid(row=1, column=1, sticky="ns")

        # Inner frame for test case widgets
        self.test_cases_frame = ttk.Frame(self.test_canvas, style="CanvasHost.TFrame")
        inner_window_id = self.test_canvas.create_window((0, 0), window=self.test_cases_frame, anchor="nw")

        # Update canvas size when inner frame changes
        def _on_frame_config(event):
            self.test_canvas.configure(scrollregion=self.test_canvas.bbox("all"))
            self.test_canvas.itemconfigure(inner_window_id, width=event.width)

        self.test_cases_frame.bind("<Configure>", _on_frame_config)
        
        # Add default test case
        self.add_test_case()



       

       
        # Options Section
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding=str(UIConfig.STANDARD_PADDING))
        options_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=UIConfig.SECTION_PADDING_Y)
        
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
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=str(UIConfig.STANDARD_PADDING))
        results_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=UIConfig.SECTION_PADDING_Y)
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
            results_frame, height=UIConfig.RESULTS_HEIGHT, font=UIConfig.MONO_FONT
        )
        self.results_text.configure(
            bg=UIConfig.ENTRY_BG, 
            fg=UIConfig.FG_COLOR, 
            insertbackground=UIConfig.FG_COLOR,
            selectbackground=UIConfig.SELECTION_BG,
            highlightthickness=1,
            highlightbackground=UIConfig.BORDER_COLOR,
            highlightcolor=UIConfig.ACCENT_COLOR,
            relief="flat"
        )
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

    def _configure_styles(self):
        """Configure common styles for consistency with Tokyo Night theme.
        
        Returns:
            ttk.Style: The configured style object
        """
        style = ttk.Style(self.root)
        
        # Configure global theme colors using 'clam' as base if available for better control
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass  # Fallback to default
            
        # Common configurations
        style.configure(".", 
            background=UIConfig.BG_COLOR, 
            foreground=UIConfig.FG_COLOR, 
            fieldbackground=UIConfig.ENTRY_BG,
            font=("Arial", 11)  # slightly larger default font
        )
        
        # Frame and Label Styling
        style.configure("TFrame", background=UIConfig.BG_COLOR)
        style.configure("TLabelframe", 
            background=UIConfig.BG_COLOR, 
            foreground=UIConfig.FG_COLOR, 
            bordercolor=UIConfig.BORDER_COLOR,
            lightcolor=UIConfig.BORDER_COLOR,
            darkcolor=UIConfig.BORDER_COLOR,
            borderwidth=1
        )
        style.configure("TLabelframe.Label", background=UIConfig.BG_COLOR, foreground=UIConfig.ACCENT_COLOR, font=("Arial", 12, "bold"))
        style.configure("TLabel", background=UIConfig.BG_COLOR, foreground=UIConfig.FG_COLOR)
        
        # Button Styling
        style.configure("TButton", 
            background=UIConfig.BUTTON_BG, 
            foreground=UIConfig.BUTTON_FG, 
            borderwidth=0,
            focusthickness=0,
            focuscolor=UIConfig.ACCENT_COLOR,
            relief="flat",
            padding=6
        )
        style.map("TButton",
            background=[("active", UIConfig.BUTTON_HOVER), ("pressed", UIConfig.ACCENT_COLOR)],
            foreground=[("pressed", UIConfig.BG_COLOR)]
        )
        
        # Entry Styling
        style.configure("TEntry", 
            fieldbackground=UIConfig.ENTRY_BG,
            foreground=UIConfig.ENTRY_FG,
            insertcolor=UIConfig.FG_COLOR,
            borderwidth=1,
            relief="flat",
            padding=5,
            bordercolor=UIConfig.BORDER_COLOR,
            lightcolor=UIConfig.BORDER_COLOR,
            darkcolor=UIConfig.BORDER_COLOR
        )
        
        # Scrollbar Styling
        style.configure("Vertical.TScrollbar", 
            background=UIConfig.PANEL_BG,
            troughcolor=UIConfig.BG_COLOR,
            borderwidth=0,
            arrowcolor=UIConfig.ACCENT_COLOR
        )
        
        # Checkbutton & Radiobutton
        style.configure("TCheckbutton", background=UIConfig.BG_COLOR, foreground=UIConfig.FG_COLOR)
        style.configure("TRadiobutton", background=UIConfig.BG_COLOR, foreground=UIConfig.FG_COLOR)

        # Store default bg for non-ttk widgets
        self.default_bg = UIConfig.BG_COLOR
            
        # Custom style for inner canvas frame
        style.configure("CanvasHost.TFrame", background=UIConfig.BG_COLOR)
        
        return style

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

    # ============================================================================
    # MODE AND PATH HANDLING
    # ============================================================================

    def on_mode_change(self):
        """Handle mode change between file and folder."""
        mode = self.mode.get()
        if mode == "file":
            self.base_entry.config(state="normal")
            self.assignment_entry.config(state="normal")
        else:
            self.base_entry.config(state="normal")
            self.assignment_entry.config(state="normal")
        
    def browse_base_solution(self):
        """Browse and select the base solution file or folder."""
        mode = self.mode.get()
        if mode == "file":
            path = filedialog.askopenfilename(title="Select Base Solution File", filetypes=[("Python files", "*.py")])
        else:
            path = filedialog.askdirectory(title="Select Base Solution Folder")
        if path:
            self.base_solution_path.set(path)
            
    def browse_assignment_path(self):
        """Browse and select the assignment folder containing student submissions."""
        mode = self.mode.get()
        if mode == "file":
            path = filedialog.askdirectory(title="Select Assignment Folder (contains Python files)")
        else:
            path = filedialog.askdirectory(title="Select Assignment Folder")
        if path:
            self.assignment_folder_path.set(path)
            
    def browse_utility_path(self):
        """Browse and select the utility folder (e.g., for graphics.py or other helper modules)."""
        path = filedialog.askdirectory(title="Select Utility Folder (e.g., graphics.py)")
        if path:
            self.utility_path.set(path)

    # ============================================================================
    # TEST CASE MANAGEMENT
    # ============================================================================

    def add_test_case(self):
        """Add a new test case input field to the test cases section."""
        test_case = TestCaseFrame(self.test_cases_frame, len(self.test_cases), self)
        test_case.grid(row=len(self.test_cases), column=0, sticky=(tk.W, tk.E), pady=2)
        self.test_cases.append(test_case)

    def clear_test_cases(self):
        """Clear all test cases and add a fresh default test case."""
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
        """Get all valid test cases from the test case widgets.
        
        Returns:
            list: List of test case dictionaries with input data
        """
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
        
    # ============================================================================
    # AUTOGRADER EXECUTION
    # ============================================================================

    def run_autograder(self):
        """Start the autograder process in a separate thread."""
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
        """Stop the currently running autograder process."""
        self.is_running = False
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set("Stopped")
        self.status_var.set("Autograder stopped")
        
    def run_autograder_thread(self):
        """Execute the grading process in a background thread."""
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
        """Find all student submission folders or files.
        
        Returns:
            list: List of paths to student submissions
        """
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
        """Run a solution (base or student) against all test cases.
        
        Args:
            path: Path to solution file or folder
            test_cases: List of test cases to run
            name: Name of the solution/student for reporting
            
        Returns:
            list: List of result dictionaries
        """
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
        """Find the main Python script in a folder.
        
        Args:
            folder_path: Path to the folder to search
            
        Returns:
            str: Path to the main script, or None if not found
        """
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
        """Execute a Python script with given input.
        
        Args:
            script_path: Path to the script to execute
            input_data: list of strings to feed to stdin
            working_dir: Directory to run the script in
            
        Returns:
            str: Stdout content
            
        Raises:
            Exception: If execution fails or times out
        """
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
            
    # ============================================================================
    # RESULT PROCESSING AND COMPARISON
    # ============================================================================

    def compare_results(self, base_results, student_results, student_name):
        """Compare student results with base results and update UI.
        
        Args:
            base_results: Results from the base/solution code
            student_results: Results from the student submission
            student_name: Name of the student/submission for reporting
        """
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
        """Show detailed output analysis for debugging including diffs.
        
        Args:
            base_result: Result dict from base solution
            student_result: Result dict from student submission
            student_name: Name of student
            test_num: Test case number
        """
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
        """Show basic discrepancy analysis for output mismatches.
        
        Args:
            base_result: Result dict from base solution
            student_result: Result dict from student submission
            student_name: Name of student
            test_num: Test case number
        """
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
        """Compare two outputs, accounting for formatting differences.
        
        Args:
            output1: First output string
            output2: Second output string
            
        Returns:
            bool: True if outputs match after normalization
        """
        if not output1 or not output2:
            return False
            
        # Normalize outputs
        norm1 = self.normalize_output(output1)
        norm2 = self.normalize_output(output2)
        
        # Compare normalized outputs
        return norm1 == norm2
        
    def normalize_output(self, output):
        """Normalize output for comparison by removing extra whitespace.
        
        Args:
            output: Raw output string
            
        Returns:
            list: List of normalized lines
        """
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
        """Run tests on a single selected student submission for debugging."""
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
        """Show a dialog for selecting a specific student submission.
        
        Args:
            student_files: List of file paths to choose from
            
        Returns:
            str: Selected file path or None if cancelled
        """
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
        
    # ============================================================================
    # UI UTILITIES
    # ============================================================================

    def update_results(self, text):
        """Update the results text area safely from any thread.
        
        Args:
            text: Text to append to the results area
        """
        self.root.after(0, lambda: self.results_text.insert(tk.END, text))
        self.root.after(0, lambda: self.results_text.see(tk.END))
        
    def clear_results(self):
        """Clear the results text area"""
        self.results_text.delete(1.0, tk.END)
        
    def open_results_window(self):
        """Open a new detailed window displaying the current results."""
        results_window = tk.Toplevel(self.root)
        results_window.title("Autograder Results - Detailed View")
        results_window.geometry(f"{UIConfig.RESULTS_WINDOW_WIDTH}x{UIConfig.RESULTS_WINDOW_HEIGHT}")
        results_window.resizable(True, True)

        window_frame = ttk.Frame(results_window)
        window_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        controls_frame = ttk.Frame(window_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        text_frame = ttk.Frame(window_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        results_window_text = tk.Text(text_frame, wrap="none", font=UIConfig.MONO_FONT) # Use 'none' for wrap to make horizontal scrollbar useful
        v_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=results_window_text.yview)
        h_scrollbar = ttk.Scrollbar(text_frame, orient="horizontal", command=results_window_text.xview)
        results_window_text.configure(
            yscrollcommand=v_scrollbar.set, 
            xscrollcommand=h_scrollbar.set,
            bg=UIConfig.ENTRY_BG,
            fg=UIConfig.FG_COLOR,
            insertbackground=UIConfig.FG_COLOR,
            selectbackground=UIConfig.SELECTION_BG,
            highlightthickness=1,
            highlightbackground=UIConfig.BORDER_COLOR,
            highlightcolor=UIConfig.ACCENT_COLOR,
            relief="flat"
        )
        
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
        """Save text content to a file using a save dialog.
        
        Args:
            content: Text content to save
        """
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
        """Copy text to the system clipboard.
        
        Args:
            text: Text to copy
        """
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Success", "Text copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard: {str(e)}")
            



class TestCaseFrame(ttk.Frame):
    """A widget frame representing a single test case input."""
    
    def __init__(self, parent, index, autograder_gui):
        """Initialize the test case frame.
        
        Args:
            parent: Parent widget
            index: Index of this test case
            autograder_gui: Reference to main GUI instance
        """
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
        self.input_text.configure(
            bg=UIConfig.ENTRY_BG, 
            fg=UIConfig.FG_COLOR, 
            insertbackground=UIConfig.FG_COLOR,
            selectbackground=UIConfig.SELECTION_BG,
            font=UIConfig.MONO_FONT,
            highlightthickness=1,
            highlightbackground=UIConfig.BORDER_COLOR,
            highlightcolor=UIConfig.ACCENT_COLOR,
            relief="flat"
        )
        
        # Remove button
        ttk.Button(self, text="Remove", command=self.remove).grid(row=0, column=2, padx=(5, 0))
        
        # Configure grid
        self.columnconfigure(1, weight=1)
        
        # Add placeholder text
        self.input_text.insert(tk.END, "Enter test input here...")
        self.input_text.bind("<FocusIn>", self.on_focus_in)
        self.input_text.bind("<FocusOut>", self.on_focus_out)
        self.input_text.configure(fg=UIConfig.BORDER_COLOR)  # Start with dim placeholder color
        self.placeholder_text = "Enter test input here..."
        self.has_content = False
        
        
    def on_focus_in(self, event):
        """Handle focus in event to clear placeholder text."""
        if not self.has_content:
            self.input_text.delete(1.0, tk.END)
            self.input_text.configure(fg=UIConfig.ENTRY_FG)
            
    def on_focus_out(self, event):
        """Handle focus out event to restore placeholder if empty."""
        if not self.input_text.get(1.0, tk.END).strip():
            self.input_text.insert(tk.END, self.placeholder_text)
            self.input_text.configure(fg=UIConfig.BORDER_COLOR)  # Use dim color for placeholder
            self.has_content = False
        else:
            self.has_content = True
        
    def is_valid(self):
        """Check if test case has valid content.
        
        Returns:
            bool: True if content exists and is not placeholder
        """
        content = self.input_text.get(1.0, tk.END).strip()
        return bool(content) and content != self.placeholder_text
        
    def get_data(self):
        """Get the test case data.
        
        Returns:
            dict: Dictionary containing input list
        """
        input_text = self.input_text.get(1.0, tk.END).strip()
        if input_text == self.placeholder_text:
            return {"input": []}
        return {
            "input": input_text.split('\n') if input_text else []
        }
        
    def remove(self):
        """Remove this test case widget from the GUI."""
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