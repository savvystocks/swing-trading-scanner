@echo off
cd /d "C:\Users\savva\OneDrive\Documents\Swing Trading"
"C:\Users\savva\AppData\Local\Programs\Python\Python311\python.exe" poller.py --once >> "data\poller.log" 2>&1
