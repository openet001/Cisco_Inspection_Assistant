import os
import re
import time
import paramiko
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from datetime import datetime
import requests
import json
import threading
import webbrowser  # 添加了这行导入
os.environ['NO_PROXY'] = 'dashscope.aliyuncs.com'

# 配置文件
CONFIG = {
    "qianwen_api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
    "qianwen_api_key": "sk-4f82962d35cc40c4ae92e6af7560dda",  # 过引号内替换为你的通义千问API密钥
    "ssh_timeout": 10,
    "username": "admin",  # 默认SSH用户名
    "password": "admin@123"  # 默认SSH密码
}

class CiscoSwitchInspector:
    def __init__(self, root):
        self.root = root
        self.root.title("思科交换机巡检与健康分析工具 Ver 1.0 Contact: 847297@qq.com")
        self.root.geometry("1000x700")
        
        # 创建日志目录
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 初始化变量
        self.switch_list = []
        self.current_switch = None
        self.ssh_client = None
        self.running = False
        
        # 创建UI
        self.create_widgets()
        
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # 右侧输出面板
        output_frame = ttk.LabelFrame(main_frame, text="输出信息", padding=10)
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 控制面板内容
        # 交换机列表文件选择
        ttk.Label(control_frame, text="交换机列表文件:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.switch_file_entry = ttk.Entry(control_frame, width=30)
        self.switch_file_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Button(control_frame, text="浏览...", command=self.browse_switch_file).grid(row=0, column=2, padx=5)
        
        # 认证信息
        ttk.Label(control_frame, text="SSH用户名:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(control_frame, width=30)
        self.username_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        self.username_entry.insert(0, CONFIG["username"])
        
        ttk.Label(control_frame, text="SSH密码:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(control_frame, width=30, show="*")
        self.password_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        self.password_entry.insert(0, CONFIG["password"])
        
        # 通义千问API密钥
        ttk.Label(control_frame, text="通义千问API密钥:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.api_key_entry = ttk.Entry(control_frame, width=30)
        self.api_key_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
        self.api_key_entry.insert(0, CONFIG["qianwen_api_key"])
        ttk.Button(
            control_frame, 
            text="申请密匙", 
            command=lambda: self.open_browser("https://bailian.console.aliyun.com/?tab=model#/api-key")
        ).grid(row=3, column=2, padx=5)
        
        # 交换机列表显示
        ttk.Label(control_frame, text="交换机列表:").grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.switch_listbox = tk.Listbox(control_frame, height=10, width=40)
        self.switch_listbox.grid(row=5, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        
        # 操作按钮
        ttk.Button(control_frame, text="加载交换机列表", command=self.load_switch_list).grid(row=6, column=0, columnspan=3, pady=10, sticky=tk.W+tk.E)
        ttk.Button(control_frame, text="开始巡检", command=self.start_inspection).grid(row=7, column=0, columnspan=3, pady=5, sticky=tk.W+tk.E)
        ttk.Button(control_frame, text="停止巡检", command=self.stop_inspection).grid(row=8, column=0, columnspan=3, pady=5, sticky=tk.W+tk.E)
        
        # 进度条
        self.progress = ttk.Progressbar(control_frame, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.progress.grid(row=9, column=0, columnspan=3, pady=10, sticky=tk.W+tk.E)
        
        # 输出面板内容
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=30)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪，本软件仅供个人测试，请注意务必在测试环境测试OK后方可对生产网络环境进行使用")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN).pack(side=tk.BOTTOM, fill=tk.X)

    def open_browser(self, url):
        try:
            webbrowser.open(url)
            self.log_output(f"已打开浏览器访问: {url}")
        except Exception as e:
            self.log_output(f"打开浏览器失败: {str(e)}")
            messagebox.showerror("错误", f"无法打开浏览器: {str(e)}")
    
        
    def browse_switch_file(self):
        filename = filedialog.askopenfilename(title="选择交换机列表文件", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if filename:
            self.switch_file_entry.delete(0, tk.END)
            self.switch_file_entry.insert(0, filename)
    
    def load_switch_list(self):
        filename = self.switch_file_entry.get()
        if not filename:
            messagebox.showerror("错误", "请先选择交换机列表文件")
            return
            
        try:
            with open(filename, 'r') as f:
                self.switch_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            self.switch_listbox.delete(0, tk.END)
            for switch in self.switch_list:
                self.switch_listbox.insert(tk.END, switch)
                
            self.update_status(f"成功加载 {len(self.switch_list)} 台交换机，请注意务必在测试环境测试OK后方可对生产网络环境进行使用")
            self.log_output(f"交换机列表已加载，共 {len(self.switch_list)} 台设备")
        except Exception as e:
            messagebox.showerror("错误", f"加载交换机列表失败: {str(e)}")
    
    def start_inspection(self):
        if not self.switch_list:
            messagebox.showerror("错误", "请先加载交换机列表")
            return
            
        if self.running:
            messagebox.showwarning("警告", "巡检已在运行中")
            return
            
        # 更新配置
        CONFIG["username"] = self.username_entry.get()
        CONFIG["password"] = self.password_entry.get()
        CONFIG["qianwen_api_key"] = self.api_key_entry.get()
        
        self.running = True
        self.progress["maximum"] = len(self.switch_list)
        self.progress["value"] = 0
        
        # 在新线程中运行巡检
        inspection_thread = threading.Thread(target=self.run_inspection, daemon=True)
        inspection_thread.start()
    
    def stop_inspection(self):
        self.running = False
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
        self.update_status("巡检已停止")
    
    def run_inspection(self):
        self.log_output("=== 开始交换机巡检 ===")
        
        for i, switch in enumerate(self.switch_list):
            if not self.running:
                break
                
            self.current_switch = switch
            self.update_status(f"正在巡检: {switch} ({i+1}/{len(self.switch_list)})")
            self.progress["value"] = i + 1
            self.root.update()
            
            try:
                # 连接交换机
                self.log_output(f"\n[开始] 连接交换机: {switch}")
                ssh = self.connect_switch(switch)
                if not ssh:
                    continue
                
                # 获取配置信息
                self.log_output(f"\n[开始] 获取交换机配置: {switch}")
                config_data = self.get_switch_config(ssh)
                
                # 保存原始配置
                self.save_config_to_file(switch, config_data)
                
                # 使用通义千问分析
                self.log_output(f"\n[开始] 使用通义千问分析交换机状态: {switch}")
                analysis_result = self.analyze_with_qianwen(switch, config_data)
                
                # 保存分析结果
                self.save_analysis_to_file(switch, analysis_result)
                
                # 显示分析结果
                self.log_output(f"\n[分析结果] {switch}:\n{analysis_result}")
                
                # 关闭连接
                ssh.close()
                self.log_output(f"\n[完成] 交换机巡检完成: {switch}")
                
            except Exception as e:
                self.log_output(f"\n[错误] 巡检交换机 {switch} 时出错: {str(e)}")
                if self.ssh_client:
                    try:
                        self.ssh_client.close()
                    except:
                        pass
        
        self.running = False
        self.current_switch = None
        self.update_status("巡检完成" if self.progress["value"] == len(self.switch_list) else "巡检已停止")
        self.log_output("\n====本次交换机巡检结束 ，请至logs目录查看对应结果文件====")
    
    def connect_switch(self, switch_ip):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=switch_ip,
                username=CONFIG["username"],
                password=CONFIG["password"],
                timeout=CONFIG["ssh_timeout"]
            )
            
            # 获取设备基本信息
            shell = self.ssh_client.invoke_shell()
            shell.send("terminal length 0\n")
            time.sleep(1)
            
            self.log_output(f"成功连接到交换机: {switch_ip}")
            return self.ssh_client
            
        except Exception as e:
            self.log_output(f"连接交换机 {switch_ip} 失败: {str(e)}")
            return None
    
    def get_switch_config(self, ssh_client):
        config_data = {
            "hostname": "",
            "show_running_config": "",
            "show_logging": "",
            "show_int_status": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            shell = ssh_client.invoke_shell()
            shell.send("terminal length 0\n")
            time.sleep(1)
            
            # 获取主机名
            shell.send("show running-config | include hostname\n")
            time.sleep(1)
            output = shell.recv(65535).decode('utf-8')
            hostname_match = re.search(r'hostname\s+(\S+)', output)
            if hostname_match:
                config_data["hostname"] = hostname_match.group(1)
            
            # 获取running-config
            self.log_output("正在获取 running-config...")
            shell.send("show running-config\n")
            time.sleep(5)  # 给足够的时间获取完整配置
            output = ""
            while True:
                if shell.recv_ready():
                    output += shell.recv(65535).decode('utf-8')
                else:
                    break
            config_data["show_running_config"] = output
            
            # 获取logging信息
            self.log_output("正在获取 logging信息...")
            shell.send("show logging\n")
            time.sleep(3)
            output = ""
            while True:
                if shell.recv_ready():
                    output += shell.recv(65535).decode('utf-8')
                else:
                    break
            config_data["show_logging"] = output
            
            # 获取接口状态
            self.log_output("正在获取接口状态...")
            shell.send("show interface status\n")
            time.sleep(2)
            output = shell.recv(65535).decode('utf-8')
            config_data["show_int_status"] = output
            
            self.log_output("成功获取交换机配置信息")
            return config_data
            
        except Exception as e:
            self.log_output(f"获取交换机配置失败: {str(e)}")
            return config_data
    
    def analyze_with_qianwen(self, switch_ip, config_data):
        prompt = f"""你是一个专业的网络工程师，请分析以下思科交换机的配置和状态信息，给出健康检查报告。
        
交换机IP: {switch_ip}
主机名: {config_data['hostname']}
检查时间: {config_data['timestamp']}

请重点分析以下方面:
1. 设备基本信息(型号、版本等)
2. 关键配置检查(如AAA、SNMP、NTP等)
3. 接口状态分析(异常接口、错误计数等)
4. 日志中的关键错误和告警
5. 整体健康状态评估和建议

以下是交换机的配置信息:
=== show running-config ===
{config_data['show_running_config'][:10000]}... (截断)

=== show logging ===
{config_data['show_logging'][:10000]}... (截断)

=== show interface status ===
{config_data['show_int_status'][:2000]}... (截断)

请用专业且简洁的语言给出分析报告，使用Markdown格式，包含章节标题和关键点列表。"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CONFIG['qianwen_api_key']}"
            }
            
            data = {
                "model": "qwen-max",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                },
                "parameters": {
                    "result_format": "message"
                }
            }
            
            self.log_output("正在调用通义千问API进行分析，如果链接千问超时或者失败，可多运行几次试试，并检查API_KEY正确，或者去阿里百链付费使用API...")
            response = requests.post(CONFIG["qianwen_api_url"], 
                       headers=headers, 
                       json=data, 
                       timeout=(20, 60))  # 连接超时20秒，读取超时60秒
            response.raise_for_status()
            
            result = response.json()
            if "output" in result and "choices" in result["output"]:
                analysis = result["output"]["choices"][0]["message"]["content"]
                return analysis
            else:
                return "通义千问分析失败: 无法解析API响应"
                
        except Exception as e:
            return f"通义千问分析失败: {str(e)}"
    
    def save_config_to_file(self, switch_ip, config_data):
        try:
            # 创建以IP为名的子目录
            ip_dir = os.path.join(self.log_dir, switch_ip)
            os.makedirs(ip_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(ip_dir, f"{switch_ip}_{timestamp}_config.txt")
            
            # 写入文件
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"=== 交换机配置检查 ===\n")
                f.write(f"IP地址: {switch_ip}\n")
                f.write(f"主机名: {config_data['hostname']}\n")
                f.write(f"检查时间: {config_data['timestamp']}\n\n")
                
                f.write("=== show running-config ===\n")
                f.write(config_data['show_running_config'])
                f.write("\n\n=== show logging ===\n")
                f.write(config_data['show_logging'])
                f.write("\n\n=== show interface status ===\n")
                f.write(config_data['show_int_status'])
            
            self.log_output(f"交换机配置已保存到: {filename}")
            
        except Exception as e:
            self.log_output(f"保存交换机配置失败: {str(e)}")
    
    def save_analysis_to_file(self, switch_ip, analysis_result):
        try:
            # 创建以IP为名的子目录
            ip_dir = os.path.join(self.log_dir, switch_ip)
            os.makedirs(ip_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(ip_dir, f"{switch_ip}_{timestamp}_analysis.txt")
            
            # 写入文件
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"=== 交换机健康分析报告 ===\n")
                f.write(f"IP地址: {switch_ip}\n")
                f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(analysis_result)
            
            self.log_output(f"分析结果已保存到: {filename}")
            
        except Exception as e:
            self.log_output(f"保存分析结果失败: {str(e)}")
    
    def log_output(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.root.update()
    
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update()

if __name__ == "__main__":
    root = tk.Tk()
    app = CiscoSwitchInspector(root)
    root.mainloop()
