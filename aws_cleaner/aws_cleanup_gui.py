import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import configparser
import threading
import logging
import boto3

# Set up logging
logging.basicConfig(
    filename='aws_cleanup.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)

logger = logging.getLogger(__name__)

class AWSCleanerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AWS Resource Cleaner")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # Variables
        self.profile_var = tk.StringVar()
        self.dry_run_var = tk.BooleanVar(value=True)  # Default to Dry Run for safety
        
        self.resource_vars = {
            "EC2": tk.BooleanVar(),
            "S3": tk.BooleanVar(),
            "Lambda": tk.BooleanVar(),
            "CloudFormation": tk.BooleanVar(),
            "RDS": tk.BooleanVar(),
            "VPC": tk.BooleanVar(),
            "IAM": tk.BooleanVar()
        }
        
        self.profiles = self.get_aws_profiles()
        self.create_widgets()
        
    def get_aws_profiles(self):
        """Read AWS profiles from credentials file"""
        profiles = []
        config = configparser.ConfigParser()
        
        credentials_path = os.path.expanduser("~/.aws/credentials")
        if os.path.exists(credentials_path):
            config.read(credentials_path)
            profiles = config.sections()
            
        if not profiles:
            logger.warning("No AWS profiles found in ~/.aws/credentials")
        
        return profiles
    
    def create_widgets(self):
        """Create the GUI elements"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Profile selection
        profile_frame = ttk.LabelFrame(main_frame, text="AWS Profile", padding="10")
        profile_frame.pack(fill=tk.X, padx=5, pady=5)
        
        if self.profiles:
            self.profile_var.set(self.profiles[0])
            profile_dropdown = ttk.Combobox(profile_frame, textvariable=self.profile_var, values=self.profiles)
            profile_dropdown.pack(fill=tk.X)
        else:
            ttk.Label(profile_frame, text="No AWS profiles found. Please set up ~/.aws/credentials").pack(fill=tk.X)
        
        # Resource selection
        resource_frame = ttk.LabelFrame(main_frame, text="Resources to Clean", padding="10")
        resource_frame.pack(fill=tk.X, padx=5, pady=5)
        
        for i, (resource, var) in enumerate(self.resource_vars.items()):
            ttk.Checkbutton(resource_frame, text=resource, variable=var).grid(row=i//3, column=i%3, sticky=tk.W, padx=10, pady=5)
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Checkbutton(options_frame, text="Dry Run (simulate cleanup without making changes)", variable=self.dry_run_var).pack(anchor=tk.W)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.start_button = ttk.Button(buttons_frame, text="Start Cleanup", command=self.start_cleanup)
        self.start_button.pack(side=tk.RIGHT, padx=5)
        
        select_all_button = ttk.Button(buttons_frame, text="Select All", command=self.select_all_resources)
        select_all_button.pack(side=tk.RIGHT, padx=5)
        
        deselect_all_button = ttk.Button(buttons_frame, text="Deselect All", command=self.deselect_all_resources)
        deselect_all_button.pack(side=tk.RIGHT, padx=5)
        
        # Log output
        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # Configure text handler for logging
        self.text_handler = TextHandler(self.log_text)
        self.text_handler.setLevel(logging.INFO)
        logger.addHandler(self.text_handler)
    
    def select_all_resources(self):
        """Select all resource checkboxes"""
        for var in self.resource_vars.values():
            var.set(True)
    
    def deselect_all_resources(self):
        """Deselect all resource checkboxes"""
        for var in self.resource_vars.values():
            var.set(False)
    
    def start_cleanup(self):
        """Start the cleanup process in a separate thread"""
        profile = self.profile_var.get()
        
        if not profile:
            messagebox.showerror("Error", "Please select an AWS profile")
            return
        
        selected_resources = [name for name, var in self.resource_vars.items() if var.get()]
        
        if not selected_resources:
            messagebox.showerror("Error", "Please select at least one resource type to clean")
            return
        
        dry_run = self.dry_run_var.get()
        
        # Confirm before proceeding
        mode_str = "DRY RUN" if dry_run else "LIVE"
        warning = f"WARNING: You are about to run in {mode_str} mode!\n\n"
        if not dry_run:
            warning += "THIS WILL PERMANENTLY DELETE AWS RESOURCES!\n\n"
        
        warning += f"Profile: {profile}\nResources: {', '.join(selected_resources)}"
        
        if not messagebox.askyesno("Confirm Cleanup", warning):
            return
        
        # Disable start button during cleanup
        self.start_button.config(state=tk.DISABLED)
        
        # Start cleanup in a new thread to keep UI responsive
        self.cleanup_thread = threading.Thread(target=self.run_cleanup, args=(profile, selected_resources, dry_run))
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        # Check thread status periodically
        self.root.after(100, self.check_thread_status)
    
    def check_thread_status(self):
        """Check if the cleanup thread is still running"""
        if self.cleanup_thread.is_alive():
            self.root.after(100, self.check_thread_status)
        else:
            self.start_button.config(state=tk.NORMAL)
            messagebox.showinfo("Cleanup Complete", "The cleanup process has finished. Check the log for details.")
    
    def run_cleanup(self, profile, resources, dry_run):
        """Run the actual cleanup process"""
        try:
            logger.info(f"Starting cleanup with profile: {profile}")
            logger.info(f"Dry run mode: {dry_run}")
            logger.info(f"Selected resources: {', '.join(resources)}")
            
            # Create session
            try:
                session = boto3.Session(profile_name=profile)
                logger.info(f"Successfully created session with profile: {profile}")
            except Exception as e:
                logger.error(f"Failed to create session with profile {profile}: {str(e)}")
                return
            
            # Get all AWS regions
            try:
                ec2_client = session.client('ec2', region_name='us-east-1')
                regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
                logger.info(f"Found {len(regions)} AWS regions")
            except Exception as e:
                logger.error(f"Failed to get AWS regions: {str(e)}")
                regions = []
            
            # Import cleaner modules
            resource_modules = {}
            
            if "EC2" in resources:
                from cleaner import ec2
                resource_modules["EC2"] = ec2
            
            if "S3" in resources:
                from cleaner import s3
                resource_modules["S3"] = s3
            
            if "Lambda" in resources:
                from cleaner import lambda_module
                resource_modules["Lambda"] = lambda_module
            
            if "CloudFormation" in resources:
                from cleaner import cloudformation
                resource_modules["CloudFormation"] = cloudformation
            
            if "RDS" in resources:
                from cleaner import rds
                resource_modules["RDS"] = rds
            
            if "VPC" in resources:
                from cleaner import vpc
                resource_modules["VPC"] = vpc
            
            if "IAM" in resources:
                from cleaner import iam
                resource_modules["IAM"] = iam
            
            # IAM is a global service, handle it separately
            if "IAM" in resources:
                logger.info("Cleaning IAM resources (global service)...")
                try:
                    resource_modules["IAM"].clean(session, dry_run=dry_run)
                except Exception as e:
                    logger.error(f"Error cleaning IAM resources: {str(e)}")
            
            # Clean resources in each region
            for region in regions:
                logger.info(f"Processing region: {region}")
                
                for resource_name, module in resource_modules.items():
                    # Skip IAM for region-based cleaning
                    if resource_name == "IAM":
                        continue
                    
                    logger.info(f"Cleaning {resource_name} resources in {region}...")
                    try:
                        module.clean(region, session, dry_run=dry_run)
                    except Exception as e:
                        logger.error(f"Error cleaning {resource_name} in {region}: {str(e)}")
            
            logger.info("Cleanup process completed")
            
        except Exception as e:
            logger.error(f"Cleanup process failed with error: {str(e)}")


class TextHandler(logging.Handler):
    """Handler for redirecting logs to the scrolled text widget"""
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    def emit(self, record):
        msg = self.formatter.format(record)
        
        def append():
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)  # Auto-scroll to the bottom
            self.text_widget.config(state=tk.DISABLED)
        
        # Schedule the update on the main thread
        self.text_widget.after(0, append)


if __name__ == "__main__":
    root = tk.Tk()
    app = AWSCleanerGUI(root)
    root.mainloop() 