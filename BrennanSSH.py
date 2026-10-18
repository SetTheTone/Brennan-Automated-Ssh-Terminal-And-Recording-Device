import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import paramiko
import threading
import os
import time
import urllib.request
import json
import webbrowser
import argparse

APP_VERSION = "v0.6.1" # Set to older version number to test the popup

class BrennanSSHGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Brennan SSH Support Ver: {APP_VERSION}")
        self.root.geometry("1200x900")
        
        self.client = None
        self.shell = None
        
        # State Tracking for Auto-Reconnect
        self.is_rebooting = False
        self.current_ip = ""

        # Top Frame: Connection controls
        top_frame = tk.Frame(root)
        top_frame.pack(pady=10, padx=10, fill=tk.X)

        tk.Label(top_frame, text="Brennan IP:").pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(top_frame, width=20)
        self.ip_entry.pack(side=tk.LEFT, padx=10)
        self.ip_entry.bind("<Return>", lambda e: self.start_connection())
        
        self.connect_btn = tk.Button(top_frame, text="Connect", command=self.start_connection)
        self.connect_btn.pack(side=tk.LEFT)

        # Quick Actions Frame
        action_frame = tk.Frame(root)
        action_frame.pack(pady=5, padx=10, fill=tk.X)
        
        tk.Label(action_frame, text="Quick Actions:").pack(side=tk.LEFT)
        
        self.reboot_btn = tk.Button(action_frame, text="Reboot", state=tk.DISABLED, 
                                    command=self.trigger_reboot)
        self.reboot_btn.pack(side=tk.LEFT, padx=5)

        self.update_btn = tk.Button(action_frame, text="Update (soon?)", state=tk.DISABLED, 
                                    command=lambda: self.send_quick_command("Hoping to suss this out"))
        self.update_btn.pack(side=tk.LEFT, padx=5)
        
        self.stats_btn = tk.Button(action_frame, text="Stats", state=tk.DISABLED, 
                                     command=self.trigger_stats)
        self.stats_btn.pack(side=tk.LEFT, padx=5)

        self.storage_btn = tk.Button(action_frame, text="Drive Stats", state=tk.DISABLED, 
                                    command=lambda: self.send_quick_command("df -h && fdisk -l"))
        self.storage_btn.pack(side=tk.LEFT, padx=5)
        
        self.dac_btn = tk.Button(action_frame, text="DAC Version", state=tk.DISABLED, 
                                    command=lambda: self.send_quick_command("aplay -l"))
        self.dac_btn.pack(side=tk.LEFT, padx=5)
        
        self.dl_settings_btn = tk.Button(action_frame, text="Settings", state=tk.DISABLED, 
                                    command=lambda: self.download_file("/media/hdd1/b2settings", "b2settings.txt"))
        self.dl_settings_btn.pack(side=tk.LEFT, padx=5)

        self.dl_b2db_btn = tk.Button(action_frame, text="b2db", state=tk.DISABLED, 
                                     command=lambda: self.download_file("/media/hdd1/b2db", "b2db.txt"))
        self.dl_b2db_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = tk.Button(action_frame, text="Export Output", command=self.export_output)
        self.export_btn.pack(side=tk.RIGHT, padx=5)

        # Middle Frame: Terminal Output
        self.text_area = scrolledtext.ScrolledText(root, bg="black", fg="lightgray", font=("Consolas", 10))
        self.text_area.pack(padx=10, fill=tk.BOTH, expand=True)
        self.text_area.insert(tk.END, "Ready. Enter IP to connect...\n")
        self.text_area.config(state=tk.DISABLED)

        # Bottom Frame: Command Input
        bottom_frame = tk.Frame(root)
        bottom_frame.pack(pady=10, padx=10, fill=tk.X)

        tk.Label(bottom_frame, text="Command:").pack(side=tk.LEFT)
        self.cmd_entry = tk.Entry(bottom_frame)
        self.cmd_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        self.cmd_entry.bind("<Return>", lambda e: self.send_command())
        self.cmd_entry.config(state=tk.DISABLED)

        # THIS EXACT LINE TRIGGERS THE UPDATE CHECK WHEN THE APP OPENS
        self.check_for_updates()

    def print_to_terminal(self, text):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def start_connection(self):
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter an IP Address.")
            return

        self.current_ip = ip
        self.connect_btn.config(state=tk.DISABLED)
        self.print_to_terminal(f"\n--- Connecting to root@{ip} ---\n")
        
        threading.Thread(target=self.ssh_thread, args=(ip,), daemon=True).start()

    def trigger_reboot(self):
        if self.shell:
            self.is_rebooting = True
            self.send_quick_command("sync && sleep 5s && kill 1")

    def trigger_web_upgrade(self):
        if not self.current_ip:
            return
            
        def upgrade_task():
            try:
                self.root.after(0, self.print_to_terminal, "\n[Sending Web Upgrade command via HTTP...]\n")
                urllib.request.urlopen(f"http://{self.current_ip}/b2.cgi?cmd=webUpgrade", timeout=5)
                self.root.after(0, self.print_to_terminal, "[Web Upgrade triggered successfully. Check Brennan screen.]\n")
            except Exception as e:
                self.root.after(0, self.print_to_terminal, f"[Web Upgrade HTTP Error: {str(e)}]\n")
                
        threading.Thread(target=upgrade_task, daemon=True).start()

    def trigger_stats(self):
        if not self.current_ip:
            return
            
        def stats_task():
            try:
                self.root.after(0, self.print_to_terminal, "\n[Fetching Brennan Stats...]\n")
                
                url = f"http://{self.current_ip}/b2cgi.fcgi?getWebInfo"
                response = urllib.request.urlopen(url, timeout=5)
                raw_data = response.read().decode('utf-8')
                
                stats_json = json.loads(raw_data)
                
                formatted_stats = "\n" + "="*40 + "\n"
                formatted_stats += "          BRENNAN SYSTEM STATS\n"
                formatted_stats += "="*40 + "\n"
                
                for key, value in stats_json.items():
                    clean_key = key[0].upper() + key[1:]
                    formatted_stats += f"{clean_key:<20}: {value}\n"
                    
                formatted_stats += "="*40 + "\n\n"
                
                self.root.after(0, self.print_to_terminal, formatted_stats)
                
            except Exception as e:
                self.root.after(0, self.print_to_terminal, f"[Stats Fetch Error: {str(e)}]\n")
                
        threading.Thread(target=stats_task, daemon=True).start()

    # Version check
    def check_for_updates(self):
        api_url = "https://api.github.com/repos/SetTheTone/Brennan-Automated-Ssh-Terminal-And-Recording-Device/releases/latest"

        def update_task():
            try:
                self.root.after(0, self.print_to_terminal, "\n[Checking GitHub for updates...]\n")
                
                req = urllib.request.Request(api_url, headers={'User-Agent': 'BrennanSSH-App'})
                response = urllib.request.urlopen(req, timeout=5)
                data = json.loads(response.read().decode('utf-8'))

                latest_version = data.get("tag_name", "")
                release_page = data.get("html_url", "")
                
                self.root.after(0, self.print_to_terminal, f"[GitHub reports latest version is: {latest_version}]\n")
                
                if latest_version and latest_version != APP_VERSION:
                    def prompt_user():
                        msg = f"A new version ({latest_version}) is available!\n\nYou are currently running {APP_VERSION}.\n\nWould you like to open the download page?"
                        if messagebox.askyesno("Update Available", msg):
                            webbrowser.open(release_page)
                            
                    self.root.after(1000, prompt_user)
            except Exception as e:
                self.root.after(0, self.print_to_terminal, f"[Update Check Failed: {str(e)}]\n")

        threading.Thread(target=update_task, daemon=True).start()

    def ssh_thread(self, ip, polling_mode=False):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        if polling_mode:
            connected = False
            attempts = 0
            time.sleep(10) 
            
            while not connected and attempts < 30: 
                try:
                    self.client.connect(hostname=ip, username='root', password='brennan', timeout=5)
                    connected = True
                except Exception:
                    attempts += 1
                    time.sleep(5)
            
            if not connected:
                self.root.after(0, self.print_to_terminal, "\n--- Auto-reconnect failed. Device did not wake up in time. ---\n")
                self.root.after(0, self.disable_controls)
                return
        else:
            try:
                self.client.connect(hostname=ip, username='root', password='brennan', timeout=10)
            except Exception as e:
                self.root.after(0, self.print_to_terminal, f"\nConnection Error: {str(e)}\n")
                self.root.after(0, self.disable_controls)
                if self.client:
                    self.client.close()
                return

        try:
            self.shell = self.client.invoke_shell()
            self.root.after(0, self.enable_controls)
            
            if polling_mode:
                self.root.after(0, self.print_to_terminal, "\n--- Auto-reconnect successful ---\n")
                self.shell.send("echo 'reboot successful'\n")
            
            while True:
                data = self.shell.recv(1024)
                if not data:
                    break
                self.root.after(0, self.print_to_terminal, data.decode('utf-8', errors='replace'))
                
        except Exception as e:
            self.root.after(0, self.print_to_terminal, f"\nConnection Error: {str(e)}\n")
            
        finally:
            self.root.after(0, self.disable_controls)
            if self.client:
                self.client.close()
            
            if self.is_rebooting:
                self.is_rebooting = False
                self.root.after(0, self.print_to_terminal, "\n--- Connection dropped. Waiting for Brennan to reboot... ---\n")
                threading.Thread(target=self.ssh_thread, args=(self.current_ip, True), daemon=True).start()

    def enable_controls(self):
        self.cmd_entry.config(state=tk.NORMAL)
        self.cmd_entry.focus()
        self.reboot_btn.config(state=tk.NORMAL)
        self.update_btn.config(state=tk.NORMAL)
        self.stats_btn.config(state=tk.NORMAL)
        self.storage_btn.config(state=tk.NORMAL)
        self.dac_btn.config(state=tk.NORMAL)
        self.dl_settings_btn.config(state=tk.NORMAL) 
        self.dl_b2db_btn.config(state=tk.NORMAL) 
        self.stats_btn.config(state=tk.NORMAL)

    def disable_controls(self):
        self.connect_btn.config(state=tk.NORMAL)
        self.cmd_entry.config(state=tk.DISABLED)
        self.reboot_btn.config(state=tk.DISABLED)
        self.update_btn.config(state=tk.DISABLED)
        self.stats_btn.config(state=tk.DISABLED)
        self.storage_btn.config(state=tk.DISABLED)
        self.dac_btn.config(state=tk.DISABLED)
        self.dl_settings_btn.config(state=tk.DISABLED) 
        self.dl_b2db_btn.config(state=tk.DISABLED) 

    def send_command(self):
        if self.shell:
            cmd = self.cmd_entry.get()
            self.shell.send(cmd + "\n")
            self.cmd_entry.delete(0, tk.END)
            
    def send_quick_command(self, cmd):
        if self.shell:
            self.print_to_terminal(f"\n[Running quick action: {cmd}]\n")
            self.shell.send(cmd + "\n")

    def download_file(self, remote_path, default_filename):
        if not self.client:
            return
            
        local_path = filedialog.asksaveasfilename(
            initialfile=default_filename,
            title=f"Save {default_filename}",
            filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
        )
        
        if not local_path:
            return 
            
        def sftp_task():
            try:
                sftp = self.client.open_sftp()
                sftp.get(remote_path, local_path)
                sftp.close()
                
                # --- START PASSWORD MASKING ---
                if "b2settings" in remote_path:
                    with open(local_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()

                    for i in range(len(lines)):
                        if lines[i].strip() == "Wifi" and i + 2 < len(lines):
                            pw = lines[i+2].rstrip('\n\r')
                            if len(pw) > 2:
                                masked = pw[0] + '*' * (len(pw) - 2) + pw[-1]
                                lines[i+2] = masked + '\n'
                            break 

                    with open(local_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                # --- END PASSWORD MASKING ---
                
                success_msg = f"File saved to:\n{local_path}"
                self.root.after(0, lambda msg=success_msg: messagebox.showinfo("Download Complete", msg))
                self.root.after(0, self.print_to_terminal, f"\n[Successfully downloaded {remote_path} to your local drive]\n")
                
            except Exception as e:
                error_msg = f"Failed to download {remote_path}:\n{str(e)}"
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("Download Error", msg))

        threading.Thread(target=sftp_task, daemon=True).start()

    def export_output(self):
        try:
            output_text = self.text_area.get("1.0", tk.END)
            save_path = os.path.join(os.getcwd(), "BrennanOutput.txt") 
            
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(output_text)
                
            messagebox.showinfo("Export Successful", f"Output saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save file: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BrennanSSHGUI(root)
    root.mainloop()
