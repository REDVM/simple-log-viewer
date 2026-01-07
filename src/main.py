import glob
import os
import html
import re
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()
logs_dirs = os.getenv("LOGS_DIR", "/logs/")
ext = os.getenv("EXT", "*.log")
n_lines_default = int(os.getenv("N_LINES", 200))

def get_unique_log_map():
    all_paths = []
    for d in logs_dirs.split(","):
        for e in ext.split(","):
            all_paths.extend(glob.glob(os.path.join(d.strip(), e.strip())))
    log_map = {}
    for path in all_paths:
        parts = path.split(os.sep)
        depth, label = 1, parts[-1]
        while label in log_map and log_map[label] != path:
            depth += 1
            label = os.sep.join(parts[-depth:])
        log_map[label] = path
    return dict(sorted(log_map.items()))

def format_logs(file_path, n_lines, pattern=None):
    if not file_path or not os.path.exists(file_path):
        return "File not found."
    
    formatted_lines, chunk_size = [], 65536
    regex = None
    if pattern:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except Exception as e:
            return f"Invalid Regex: {e}"

    try:
        with open(file_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pointer, content = f.tell(), b""
            
            # Read backwards. Note: if filtering, we still grab the last n_lines total lines 
            # and then filter them to maintain performance.
            while content.count(b"\n") <= n_lines and pointer > 0:
                step = min(pointer, chunk_size)
                pointer -= step
                f.seek(pointer)
                content = f.read(step) + content
            
            lines = content.splitlines()[-n_lines:]
            for line in lines:
                decoded = line.decode("utf-8", errors="replace")
                
                # Filter logic
                if regex and not regex.search(decoded):
                    continue
                    
                safe = html.escape(decoded)
                low = safe.lower()
                if any(x in low for x in ["error", "fail"]):
                    formatted_lines.append(f'<span class="text-red-500 font-bold">{safe}</span>')
                elif any(x in low for x in ["success", "succeed"]):
                    formatted_lines.append(f'<span class="text-green-500 font-bold">{safe}</span>')
                else:
                    formatted_lines.append(safe)
                    
        return "\n".join(formatted_lines)
    except Exception as e:
        return f"Error: {e}"

@app.get("/", response_class=HTMLResponse)
async def dashboard(file: str = None, n_lines: int = Query(None), filter: str = Query(None)):
    if n_lines is None:
        n_lines = n_lines_default
    log_map = get_unique_log_map()
    current_label = file if file in log_map else (list(log_map.keys())[0] if log_map else None)
    full_path = log_map.get(current_label)
    content = format_logs(full_path, n_lines, filter)

    tabs = "".join([
        f'<a href="/?file={label}&n_lines={n_lines}{f"&filter={filter}" if filter else ""}" class="px-4 py-2 rounded-t-lg transition whitespace-nowrap {"bg-blue-600" if label == current_label else "bg-gray-700 hover:bg-gray-600"}">{label}</a>'
        for label in log_map.keys()
    ])

    return f"""
    <html>
        <head>
            <script src="https://cdn.tailwindcss.com"></script>
            <title>Log Viewer</title>
            <style>
                #log-container::-webkit-scrollbar {{ width: 8px; }}
                #log-container::-webkit-scrollbar-thumb {{ background: #4b5563; border-radius: 4px; }}
                .no-scrollbar::-webkit-scrollbar {{ display: none; }}
                input::-webkit-outer-spin-button, input::-webkit-inner-spin-button {{ -webkit-appearance: none; margin: 0; }}
                input[type=number] {{ -moz-appearance: textfield; }}
            </style>
        </head>
        <body class="bg-gray-900 text-gray-100 p-6 font-sans">
            <div class="max-w-7xl mx-auto">
                <nav class="flex space-x-2 border-b border-gray-700 overflow-x-auto no-scrollbar">{tabs}</nav>
                <main class="bg-gray-800 p-6 rounded-b-xl border border-t-0 border-gray-700 shadow-2xl">
                    <div id="log-container" class="w-full h-[800px] bg-black font-mono text-sm p-4 rounded overflow-y-auto whitespace-pre-wrap">{content}</div>
                    
                    <div class="mt-4 flex justify-between items-center">
                        <form action="/" method="get" class="flex items-center space-x-4">
                            <input type="hidden" name="file" value="{current_label or ''}">
                            <div class="flex items-center space-x-2">
                                <span class="text-[10px] text-gray-500 uppercase font-bold">Lines</span>
                                <input type="number" name="n_lines" value="{n_lines}" class="bg-gray-700 text-white text-xs px-2 py-1 rounded border border-gray-600 w-16 text-center outline-none">
                            </div>
                            <div class="flex items-center space-x-2">
                                <span class="text-[10px] text-gray-500 uppercase font-bold">Regex Filter</span>
                                <input type="text" name="filter" value="{filter or ''}" placeholder=".*" class="bg-gray-700 text-white text-xs px-3 py-1 rounded border border-gray-600 w-48 outline-none focus:border-blue-500">
                            </div>
                            <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white text-xs px-4 py-1 rounded font-bold transition">Update</button>
                        </form>
                        <div class="text-right">
                            <div class="text-[10px] text-gray-500 font-mono mb-1 truncate max-w-md">{full_path or ""}</div>
                            <button onclick="location.reload()" class="bg-gray-700 hover:bg-gray-600 text-white text-xs px-4 py-1 rounded transition">Refresh</button>
                        </div>
                    </div>
                </main>
            </div>
            <script>
                const container = document.getElementById('log-container');
                container.scrollTop = container.scrollHeight;
            </script>
        </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)