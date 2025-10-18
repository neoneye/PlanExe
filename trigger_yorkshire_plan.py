#!/usr/bin/env python3
"""
Author: Cascade AI
Date: 2025-10-17
PURPOSE: Trigger a test plan for Yorkshire terrier breeding business with full streaming capture
SRP and DRY check: Pass - Single responsibility for testing plan creation with streaming
"""

import asyncio
import json
import requests
import time
from pathlib import Path
from datetime import datetime
import websockets

# Configuration
API_BASE = "http://localhost:8080"
WS_BASE = "ws://localhost:8080"
PLAN_PROMPT = "to become a Yorkshire terrier breeder"
DEFAULT_MODEL = "gpt-5-mini-2025-08-07"  # Using actual configured model from llm_config.json

def create_plan():
    """Create a new plan via REST API"""
    print("=" * 70)
    print("Creating Yorkshire Terrier Breeding Plan")
    print("=" * 70)
    
    create_data = {
        "prompt": PLAN_PROMPT,
        "speed_vs_detail": "all_details_but_slow",  # Full plan
        "model_name": DEFAULT_MODEL
    }
    
    print(f"\n📝 Plan Details:")
    print(f"   Prompt: {create_data['prompt']}")
    print(f"   Model: {create_data['model_name']}")
    print(f"   Detail Level: {create_data['speed_vs_detail']}")
    print(f"\n🚀 Sending request to {API_BASE}/api/plans...")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/plans",
            json=create_data,
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            plan_data = response.json()
            plan_id = plan_data["plan_id"]
            print(f"   ✅ Plan Created: {plan_id}")
            print(f"   Status: {plan_data['status']}")
            return plan_id
        else:
            print(f"   ❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None


async def monitor_websocket_progress(plan_id: str):
    """Monitor plan progress via WebSocket with full streaming capture"""
    
    ws_url = f"{WS_BASE}/ws/plans/{plan_id}/progress"
    
    print(f"\n📡 Connecting to WebSocket: {ws_url}")
    print("=" * 70)
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket Connected - Streaming Progress:\n")
            
            message_count = 0
            last_progress = 0
            
            while True:
                try:
                    # Receive message with timeout
                    message = await asyncio.wait_for(websocket.recv(), timeout=300.0)
                    message_count += 1
                    
                    # Parse JSON message
                    data = json.loads(message)
                    
                    # Extract event details
                    event_type = data.get("type", "unknown")
                    
                    if event_type == "progress":
                        progress = data.get("progress_percentage", 0)
                        message_text = data.get("message", "")
                        status = data.get("status", "unknown")
                        current_task = data.get("current_task", "")
                        completed_tasks = data.get("completed_tasks", 0)
                        total_tasks = data.get("total_tasks", 61)
                        
                        # Show progress bar
                        bar_length = 40
                        filled = int(bar_length * progress / 100)
                        bar = "█" * filled + "░" * (bar_length - filled)
                        
                        print(f"\r[{message_count:4d}] [{bar}] {progress:5.1f}% | {completed_tasks}/{total_tasks} | {status:12s} | {current_task[:40]:<40}", end="", flush=True)
                        
                        if progress != last_progress:
                            print()  # New line for new progress
                            if message_text:
                                print(f"       💬 {message_text}")
                            last_progress = progress
                    
                    elif event_type == "log":
                        log_message = data.get("message", "")
                        print(f"\n       📋 LOG: {log_message}")
                    
                    elif event_type == "error":
                        error_message = data.get("message", "")
                        print(f"\n       ❌ ERROR: {error_message}")
                        break
                    
                    elif event_type == "complete":
                        print(f"\n\n✅ Pipeline Complete!")
                        final_status = data.get("status", "completed")
                        print(f"   Final Status: {final_status}")
                        break
                    
                    elif event_type == "heartbeat":
                        # Silent heartbeat
                        pass
                    else:
                        print(f"\n       🔔 {event_type.upper()}: {json.dumps(data, indent=2)}")
                
                except asyncio.TimeoutError:
                    print("\n⏱️  WebSocket timeout - pipeline may still be running")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 WebSocket connection closed")
                    break
                    
    except Exception as e:
        print(f"\n❌ WebSocket Error: {e}")


def check_generated_files(plan_id: str):
    """Check for generated files in the run directory"""
    
    print("\n" + "=" * 70)
    print("Checking Generated Files")
    print("=" * 70)
    
    # Find the run directory for this plan
    run_dir = Path("run")
    
    if not run_dir.exists():
        print("❌ Run directory not found!")
        return
    
    # Find subdirectories matching the plan_id
    plan_dirs = list(run_dir.glob(f"*{plan_id}*"))
    
    if not plan_dirs:
        # Try to find by timestamp
        plan_dirs = sorted(run_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]
    
    if not plan_dirs:
        print("❌ No plan directories found!")
        return
    
    plan_dir = plan_dirs[0]
    print(f"\n📂 Plan Directory: {plan_dir}")
    
    # Check for the test files mentioned by user
    test_files = [
        "001-1-start_time.json",
        "001-2-plan.txt"
    ]
    
    print("\n🔍 Searching for key files:")
    for filename in test_files:
        filepath = plan_dir / filename
        if filepath.exists():
            print(f"   ✅ {filename} ({filepath.stat().st_size} bytes)")
            
            # Show content preview
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if len(content) < 500:
                        print(f"      Content: {content[:200]}")
                    else:
                        print(f"      Preview: {content[:200]}...")
            except Exception as e:
                print(f"      Could not read: {e}")
        else:
            print(f"   ❌ {filename} - NOT FOUND")
    
    # List all generated files
    all_files = sorted(plan_dir.glob("*.*"))
    print(f"\n📋 All Generated Files ({len(all_files)} total):")
    for filepath in all_files[:20]:  # Show first 20
        size_kb = filepath.stat().st_size / 1024
        print(f"   • {filepath.name} ({size_kb:.1f} KB)")
    
    if len(all_files) > 20:
        print(f"   ... and {len(all_files) - 20} more files")


async def main():
    """Main execution flow"""
    
    print("\n" + "🐕" * 35)
    print("Yorkshire Terrier Breeding Business Plan Generator")
    print("🐕" * 35)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Create the plan
    plan_id = create_plan()
    
    if not plan_id:
        print("\n❌ Failed to create plan. Exiting.")
        return
    
    # Wait a moment for backend to initialize
    print("\n⏳ Waiting 2 seconds for pipeline initialization...")
    await asyncio.sleep(2)
    
    # Step 2: Monitor via WebSocket
    await monitor_websocket_progress(plan_id)
    
    # Step 3: Check generated files
    check_generated_files(plan_id)
    
    # Final summary
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n💡 To view the plan, check the run/{plan_id}/ directory")
    print(f"💡 Or visit: http://localhost:3000 to see it in the UI\n")


if __name__ == "__main__":
    asyncio.run(main())
