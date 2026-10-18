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
import socket
import concurrent.futures

# --- MASTER APP SETTINGS --- 
APP_VERSION = "v0.7.0" # Set new version before pushing to GitHub
DEBUG_MODE = False     # True for Debug, False for Production 
# ---------------------------

class BrennanSSHGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Brennan SSH Support Ver: {APP_VERSION}" + (" [DEBUG MODE]" if DEBUG_MODE else ""))
        self.root.geometry("1200x900")
        
        self.client = None
        self.shell = None
        
        self.is_rebooting = False
        self.current_ip = ""

        # Top Frame
        top_frame = tk.Frame(root)
        top_frame.pack(pady=10, padx=10, fill=tk.X)

        tk.Label(top_frame, text="Brennan IP:").pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(top_frame, width=20)
        self.ip_entry.pack(side=tk.LEFT, padx=10)
        self.ip_entry.bind("<Return>", lambda e: self.start_connection())
        
        self.connect_btn = tk.Button(top_frame, text="Connect", command=self.start_connection)
        self.connect_btn.pack(side=tk.LEFT)
        
        self.scan_btn = tk.Button(top_frame, text="Scan Subnet", command=self.trigger_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        # Quick Actions Frame
        action_frame = tk.Frame(root)
        action_frame.pack(pady=5, padx=10, fill=tk.X)
        
        tk.Label(action_frame, text="Quick Actions:").pack(side=tk.LEFT)
        
        self.reboot_btn = tk.Button(action_frame, text="Reboot", state=tk.DISABLED, 
                                    command=self.trigger_reboot)
        self.reboot_btn.pack(side=tk.LEFT, padx=5)

        self.update_btn = tk.Button(action_frame, text="Sys Upd (soon?)", state=tk.DISABLED, 
                                    command=lambda: self.send_quick_command("Hoping to suss this out"))
        self.update_btn.pack(side=tk.LEFT, padx=5)

        self.radio_btn = tk.Button(action_frame, text="Radio Upd (soon?)", state=tk.DISABLED, 
                                    command=lambda: self.send_quick_command("Hoping to suss this out"))
        self.radio_btn.pack(side=tk.LEFT, padx=5) 
               
        self.stats_btn = tk.Button(action_frame, text="Stats", state=tk.DISABLED, 
                                     command=self.trigger_stats)
        self.stats_btn.pack(side=tk.LEFT, padx=5)

        self.storage_btn = tk.Button(action_frame, text="Drive Stats", state=tk.DISABLED, 
                                    command=lambda: self.send_quick_command("df -h && fdisk -l"))
        self.storage_btn.pack(side=tk.LEFT, padx=5)
        
        self.dac_btn = tk.Button(action_frame, text="DAC Ver", state=tk.DISABLED, 
                                    command=lambda: self.send_quick_command("aplay -l"))
        self.dac_btn.pack(side=tk.LEFT, padx=5)
        
        self.dl_settings_btn = tk.Button(action_frame, text="Settings", state=tk.DISABLED, 
                                    command=lambda: self.download_file("/media/hdd1/b2settings", "b2settings.txt"))
        self.dl_settings_btn.pack(side=tk.LEFT, padx=5)

        self.dl_b2db_btn = tk.Button(action_frame, text="B2DB", state=tk.DISABLED, 
                                     command=lambda: self.download_file("/media/hdd1/b2db", "b2db.txt"))
        self.dl_b2db_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = tk.Button(action_frame, text="Export Output", command=self.export_output)
        self.export_btn.pack(side=tk.RIGHT, padx=5)

        # Middle Frame
        self.text_area = scrolledtext.ScrolledText(root, bg="black", fg="lightgray", font=("Consolas", 10))
        self.text_area.pack(padx=10, fill=tk.BOTH, expand=True)
        
        # --- DEFINE COLORS FOR THE TERMINAL ---
        self.text_area.tag_config("success", foreground="#55FF55") # Bright Green
        self.text_area.tag_config("error", foreground="#FF5555")   # Bright Red
        self.text_area.tag_config("debug", foreground="#FFFF55")   # Yellow
        # --------------------------------------
        
        self.text_area.insert(tk.END, "Ready. Enter IP to connect...\n")
        self.text_area.config(state=tk.DISABLED)

        # Bottom Frame
        bottom_frame = tk.Frame(root)
        bottom_frame.pack(pady=10, padx=10, fill=tk.X)

        tk.Label(bottom_frame, text="Command:").pack(side=tk.LEFT)
        self.cmd_entry = tk.Entry(bottom_frame)
        self.cmd_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        self.cmd_entry.bind("<Return>", lambda e: self.send_command())
        self.cmd_entry.config(state=tk.DISABLED)

        self.check_for_updates()

    def debug_print(self, text):
        if DEBUG_MODE:
            self.root.after(0, lambda t=text: self.print_to_terminal(f"[DEBUG] {t}\n"))

    def print_to_terminal(self, text):
        # Print to raw console behind the scenes
        try:
            if text.strip():
                print(text.strip())
        except Exception:
            pass
        
        self.text_area.config(state=tk.NORMAL)
        
        # --- AUTO-COLOR DETECTION ---
        tag = None
        lower_text = text.lower()
        
        if "[debug]" in lower_text:
            tag = "debug"
        elif "error" in lower_text or "fail" in lower_text or "no brennan" in lower_text:
            tag = "error"
        elif "success" in lower_text:
            tag = "success"
            
        if tag:
            self.text_area.insert(tk.END, text, tag)
        else:
            self.text_area.insert(tk.END, text)
        # ----------------------------
        
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def start_connection(self):
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter an IP Address.")
            return

        self.current_ip = ip
        self.connect_btn.config(state=tk.DISABLED)
        self.scan_btn.config(state=tk.DISABLED)
        self.print_to_terminal(f"\n--- Connecting to root@{ip} ---\n")
        threading.Thread(target=self.ssh_thread, args=(ip,), daemon=True).start()
        
    def trigger_scan(self):
        self.scan_btn.config(state=tk.DISABLED)
        self.connect_btn.config(state=tk.DISABLED)
        self.print_to_terminal("\n[Starting network scan to find Brennan...]\n")
    
        def scan_task():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80)) 
                local_ip = s.getsockname()[0]
            except Exception:
                local_ip = '192.168.1.1' 
            finally:
                s.close()

            subnet = '.'.join(local_ip.split('.')[:-1]) + '.'
            self.debug_print(f"Local IP detected as {local_ip}. Scanning {subnet}x")
            self.root.after(0, lambda: self.print_to_terminal(f"[Scanning {subnet}1 through {subnet}254... Please wait...]\n"))

            found_ip = None
            
            def check_ip(ip_suffix):
                target_ip = f"{subnet}{ip_suffix}"
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5) 
                    result = sock.connect_ex((target_ip, 80))
                    sock.close()
                    
                    if result == 0:
                        self.debug_print(f"Port 80 OPEN on {target_ip}. Testing for Brennan API...")
                        url = f"http://{target_ip}/b2cgi.fcgi?getWebInfo"
                        req = urllib.request.Request(url, headers={'User-Agent': 'BrennanSSH-App'})
                        resp = urllib.request.urlopen(req, timeout=5.0) 
                        body = resp.read()
                        if b"capacity" in body or b"version" in body:
                            self.debug_print(f"Brennan signature verified on {target_ip}!")
                            return target_ip
                        else:
                            self.debug_print(f"Web server at {target_ip} is NOT a Brennan.")
                except Exception as e:
                    if 'result' in locals() and result == 0:
                        self.debug_print(f"HTTP Timeout/Error on {target_ip}: {str(e)}")
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
                futures = [executor.submit(check_ip, i) for i in range(1, 255)]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res:
                        found_ip = res
                        break 
            
            if found_ip:
                self.root.after(0, lambda: self.print_to_terminal(f"[Success! Brennan found at: {found_ip}]\n"))
                def update_ui():
                    self.ip_entry.delete(0, tk.END)
                    self.ip_entry.insert(0, found_ip)
                    self.scan_btn.config(state=tk.NORMAL)
                    self.connect_btn.config(state=tk.NORMAL)
                    
                    # --- THE NEW AUTO-CONNECT TRIGGER ---
                    self.start_connection()
                    # ------------------------------------
                    
                self.root.after(0, update_ui)
            else:
                self.root.after(0, lambda: self.print_to_terminal("[Scan complete. No Brennan device found on this subnet.]\n"))
                self.root.after(0, lambda: self.scan_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))

        threading.Thread(target=scan_task, daemon=True).start()    

    def trigger_reboot(self):
        if self.shell:
            self.is_rebooting = True
            self.send_quick_command("sync && echo s > /proc/sysrq-trigger && echo u > /proc/sysrq-trigger && echo b > /proc/sysrq-trigger")

    def trigger_stats(self):
        if not self.current_ip: return
        def stats_task():
            try:
                self.root.after(0, lambda: self.print_to_terminal("\n[Fetching Brennan Stats...]\n"))
                url = f"http://{self.current_ip}/b2cgi.fcgi?getWebInfo"
                response = urllib.request.urlopen(url, timeout=5)
                stats_json = json.loads(response.read().decode('utf-8'))
                
                formatted = "\n" + "="*40 + "\n          BRENNAN SYSTEM STATS\n" + "="*40 + "\n"
                for key, value in stats_json.items():
                    formatted += f"{(key[0].upper() + key[1:]):<20}: {value}\n"
                formatted += "="*40 + "\n\n"
                self.root.after(0, lambda f=formatted: self.print_to_terminal(f))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.print_to_terminal(f"[Stats Fetch Error: {err}]\n"))
        threading.Thread(target=stats_task, daemon=True).start()

    def check_for_updates(self):
        api_url = "https://api.github.com/repos/SetTheTone/Brennan-Automated-Ssh-Terminal-And-Recording-Device/releases/latest"
        def update_task():
            try:
                self.debug_print(f"Pinging GitHub API: {api_url}")
                req = urllib.request.Request(api_url, headers={'User-Agent': 'BrennanSSH-App'})
                response = urllib.request.urlopen(req, timeout=5)
                data = json.loads(response.read().decode('utf-8'))
                latest_version = data.get("tag_name", "")
                release_page = data.get("html_url", "")
                self.debug_print(f"GitHub returned tag: {latest_version}")
                
                active_version = "v0.0.1" if DEBUG_MODE else APP_VERSION
                
                if latest_version and latest_version != active_version:
                    def prompt_user():
                        msg = f"A new version ({latest_version}) is available!\n\nYou are currently running {APP_VERSION}.\n\nWould you like to open the download page?"
                        if messagebox.askyesno("Update Available", msg):
                            webbrowser.open(release_page)
                    self.root.after(1000, prompt_user)
            except Exception as e:
                self.debug_print(f"Update Check HTTP Error: {str(e)}")
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
                self.root.after(0, lambda: self.print_to_terminal("\n--- Auto-reconnect failed ---\n"))
                self.root.after(0, self.disable_controls)
                return
        else:
            try:
                self.client.connect(hostname=ip, username='root', password='brennan', timeout=10)
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.print_to_terminal(f"\nConnection Error: {err}\n"))
                self.root.after(0, self.disable_controls)
                if self.client: self.client.close()
                return

        try:
            self.shell = self.client.invoke_shell()
            self.root.after(0, self.enable_controls)
            if polling_mode:
                self.root.after(0, lambda: self.print_to_terminal("\n--- Auto-reconnect successful ---\n"))
                self.shell.send("echo 'reboot successful'\n")
            
            while True:
                data = self.shell.recv(1024)
                if not data: break
                self.root.after(0, lambda d=data.decode('utf-8', errors='replace'): self.print_to_terminal(d))
        except Exception as e:
            self.root.after(0, lambda err=str(e): self.print_to_terminal(f"\nConnection Error: {err}\n"))
        finally:
            self.root.after(0, self.disable_controls)
            if self.client: self.client.close()
            if self.is_rebooting:
                self.is_rebooting = False
                self.root.after(0, lambda: self.print_to_terminal("\n--- Waiting for reboot... ---\n"))
                threading.Thread(target=self.ssh_thread, args=(self.current_ip, True), daemon=True).start()

    def enable_controls(self):
        self.cmd_entry.config(state=tk.NORMAL)
        self.cmd_entry.focus()
        self.reboot_btn.config(state=tk.NORMAL)
        self.update_btn.config(state=tk.DISABLED) # Leave DISABLED awaiting code
        self.radio_btn.config(state=tk.DISABLED) # Leave DISABLED awaiting code
        self.stats_btn.config(state=tk.NORMAL)
        self.storage_btn.config(state=tk.NORMAL)
        self.dac_btn.config(state=tk.NORMAL)
        self.dl_settings_btn.config(state=tk.NORMAL) 
        self.dl_b2db_btn.config(state=tk.NORMAL) 
        self.scan_btn.config(state=tk.DISABLED)

    def disable_controls(self):
        self.connect_btn.config(state=tk.NORMAL)
        self.cmd_entry.config(state=tk.DISABLED)
        self.reboot_btn.config(state=tk.DISABLED)
        self.update_btn.config(state=tk.DISABLED)
        self.radio_btn.config(state=tk.DISABLED)
        self.stats_btn.config(state=tk.DISABLED)
        self.storage_btn.config(state=tk.DISABLED)
        self.dac_btn.config(state=tk.DISABLED)
        self.dl_settings_btn.config(state=tk.DISABLED) 
        self.dl_b2db_btn.config(state=tk.DISABLED) 
        self.scan_btn.config(state=tk.NORMAL)

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
        if not self.client: return
        local_path = filedialog.asksaveasfilename(
            initialfile=default_filename,
            title=f"Save {default_filename}",
            filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
        )
        if not local_path: return 
            
        def sftp_task():
            try:
                sftp = self.client.open_sftp()
                sftp.get(remote_path, local_path)
                sftp.close()
                if "b2settings" in remote_path:
                    with open(local_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    for i in range(len(lines)):
                        if lines[i].strip() == "Wifi" and i + 2 < len(lines):
                            pw = lines[i+2].rstrip('\n\r')
                            if len(pw) > 2:
                                lines[i+2] = pw[0] + '*' * (len(pw) - 2) + pw[-1] + '\n'
                            break 
                    with open(local_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                success_msg = f"File saved to:\n{local_path}"
                self.root.after(0, lambda msg=success_msg: messagebox.showinfo("Download Complete", msg))
                self.root.after(0, lambda: self.print_to_terminal(f"\n[Successfully downloaded {remote_path}]\n"))
            except Exception as e:
                self.root.after(0, lambda err=str(e): messagebox.showerror("Download Error", f"Failed:\n{err}"))
        threading.Thread(target=sftp_task, daemon=True).start()

    def export_output(self):
        try:
            output_text = self.text_area.get("1.0", tk.END)
            save_path = os.path.join(os.getcwd(), "BrennanOutput.txt") 
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(output_text)
            messagebox.showinfo("Export Successful", f"Output saved to:\n{save_path}")
            
            # --- AUTO-COLORED SUCCESS ECHO ---
            self.print_to_terminal(f"\n[Success! Terminal output exported to: {save_path}]\n")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save file: {e}")
            
            # --- AUTO-COLORED ERROR ECHO ---
            self.print_to_terminal(f"\n[Export Error: Failed to save file - {str(e)}]\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = BrennanSSHGUI(root)
    root.mainloop()
# hoop
