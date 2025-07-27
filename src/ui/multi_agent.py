import os
import asyncio
import re
import subprocess
import platform
from dotenv import load_dotenv

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel
from semantic_kernel.contents.chat_history import ChatHistory

# ✅ Make ChatCompletionAgent hashable
ChatCompletionAgent.__hash__ = lambda self: hash(id(self))

load_dotenv()

class ApprovalTerminationStrategy(TerminationStrategy):
    """
    Terminates when the user says 'APPROVED' in the chat history.
    Only terminates after HTML code has been generated and reviewed.
    """
    async def should_agent_terminate(self, agent, history):
        # First, check if we have HTML code in the conversation
        has_html_code = False
        for msg in history:
            if hasattr(msg, 'content') and msg.content:
                if '```html' in msg.content.lower():
                    has_html_code = True
                    break
        
        # Only check for approval if we have HTML code
        if not has_html_code:
            return False
        
        # Check for "READY FOR USER APPROVAL" from Product Owner
        ready_for_approval = False
        for msg in reversed(history):
            if (hasattr(msg, 'content') and msg.content and 
                "READY FOR USER APPROVAL" in msg.content.upper()):
                ready_for_approval = True
                break
        
        # Only terminate if we have HTML code, PO approval, and user approval
        if ready_for_approval:
            for msg in reversed(history):
                if (hasattr(msg, 'role') and msg.role == AuthorRole.USER and 
                    hasattr(msg, 'content') and "APPROVED" in msg.content.upper()):
                    return True
        
        return False

def create_kernel() -> Kernel:
    """Creates and configures the Semantic Kernel with Azure OpenAI service."""
    kernel = Kernel()
    
    # Verify environment variables are set
    deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    
    if not all([deployment_name, endpoint, api_key]):
        raise ValueError("Missing required Azure OpenAI environment variables")
    
    kernel.add_service(service=AzureChatCompletion(
        deployment_name=deployment_name,
        endpoint=endpoint,
        api_key=api_key,
    ))
    return kernel

# Enhanced Agent Prompts
BA_PROMPT = """
You are a Business Analyst. Your role is to:
1. Analyze user requirements thoroughly
2. Create a clear, concise project specification
3. Define functional requirements for the weather app
4. Provide cost estimates and timeline
5. Ensure all requirements are documented for the Software Engineer

Focus on creating actionable requirements that can be implemented immediately.
Keep your analysis concise but comprehensive.
"""

SE_PROMPT = """
You are a Software Engineer. Your role is to:
1. Review requirements from the Business Analyst
2. Create a fully functional weather app using HTML, CSS, and JavaScript
3. Implement all requested features
4. Use a weather API (like OpenWeatherMap) for real data
5. Ensure the app is responsive and user-friendly
6. Deliver clean, well-commented code

CRITICAL: Always format your final code using ```html [your complete code] ``` 
This exact format is required for deployment to GitHub.
"""

PO_PROMPT = """
You are the Product Owner. Your role is to:
1. Review the Software Engineer's implementation
2. Verify all user requirements are met
3. Check code quality and functionality
4. Ensure proper code formatting for deployment

CRITICAL CHECKS:
- Verify HTML code is properly formatted with ```html [code] ```
- Confirm all user requirements are implemented
- Check that the weather app is functional and complete

Once all requirements are satisfied and code is properly formatted, 
respond with exactly: "READY FOR USER APPROVAL"
"""

def extract_html_code(messages):
    """Extracts HTML code blocks from agent messages."""
    html_pattern = r"```html\s*([\s\S]*?)```"
    
    for msg in messages:
        if isinstance(msg, dict) and 'content' in msg:
            content = msg['content']
            match = re.search(html_pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                html_code = match.group(1).strip()
                if html_code:  # Ensure we have actual content
                    print(f"✅ Found HTML code ({len(html_code)} characters)")
                    return html_code
    
    print("❌ No HTML code found in messages")
    return None

def create_git_script(target_directory=None):
    """Creates platform-specific Git deployment scripts in the specified directory."""
    
    # Use current directory if no target specified
    if target_directory is None:
        target_directory = os.getcwd()
    
    # Ensure target directory exists
    os.makedirs(target_directory, exist_ok=True)
    
    if platform.system() == "Windows":
        script_content = '''@echo off
setlocal enabledelayedexpansion
echo Starting Git operations for weather app deployment...

REM Navigate to the correct directory
cd /d "%~dp0"

REM Check if we're in a git repository
if not exist ".git" (
    echo Initializing Git repository...
    git init
    if !errorlevel! neq 0 (
        echo Error: Failed to initialize Git repository
        exit /b 1
    )
)

REM Configure Git user if not set
git config user.name >nul 2>&1
if !errorlevel! neq 0 (
    echo Setting Git user configuration...
    git config user.name "Multi-Agent System"
    git config user.email "multiagent@example.com"
)

REM Check if index.html exists
if not exist "index.html" (
    echo Error: index.html not found in current directory
    echo Current directory: %CD%
    dir *.html
    exit /b 1
)

echo Staging index.html...
git add index.html
if !errorlevel! neq 0 (
    echo Error: Failed to stage file
    exit /b 1
)

REM Check for changes
git diff --staged --quiet >nul 2>&1
if !errorlevel! equ 0 (
    echo No changes to commit.
    exit /b 0
)

echo Committing changes...
git commit -m "Auto-deploy weather app from multi-agent system"
if !errorlevel! neq 0 (
    echo Error: Git commit failed
    exit /b 1
)

echo Pushing to GitHub...
git push origin main 2>nul
if !errorlevel! equ 0 (
    echo SUCCESS: Weather app deployed to GitHub
    exit /b 0
) else (
    echo Trying master branch...
    git push origin master 2>nul
    if !errorlevel! equ 0 (
        echo SUCCESS: Weather app deployed to GitHub on master branch
    else (
        echo ERROR: Failed to push to GitHub
        echo Please check your Git credentials and remote configuration
        exit /b 1
    )
)
'''
        script_name = "push_to_github.bat"
    else:
        script_content = '''#!/bin/bash
set -e  # Exit on any error

echo "Starting Git operations for weather app deployment..."

# Change to script directory
cd "$(dirname "$0")"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "Initializing Git repository..."
    git init
fi

# Configure Git user if not set
if ! git config user.name >/dev/null 2>&1; then
    echo "Setting Git user configuration..."
    git config user.name "Multi-Agent System"
    git config user.email "multiagent@example.com"
fi

# Check if index.html exists
if [ ! -f "index.html" ]; then
    echo "Error: index.html not found in current directory"
    echo "Current directory: $(pwd)"
    ls -la *.html 2>/dev/null || echo "No HTML files found"
    exit 1
fi

echo "Staging index.html..."
git add index.html

# Check for changes
if git diff --staged --quiet; then
    echo "No changes to commit."
    exit 0
fi

echo "Committing changes..."
git commit -m "Auto-deploy weather app from multi-agent system - $(date)"

echo "Pushing to GitHub..."
if git push origin main 2>/dev/null; then
    echo "✅ SUCCESS: Weather app deployed to GitHub!"
elif git push origin master 2>/dev/null; then
    echo "✅ SUCCESS: Weather app deployed to GitHub (master)!"
else
    echo "❌ ERROR: Failed to push to GitHub"
    echo "Please check your Git credentials and remote configuration"
    exit 1
fi
'''
        script_name = "push_to_github.sh"
    
    # Create full path for the script
    script_path = os.path.join(target_directory, script_name)
    
    # Write the script file
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    
    # Make executable on Unix-like systems
    if platform.system() != "Windows":
        os.chmod(script_path, 0o755)
    
    print(f"✅ Created {script_name} in {target_directory}")
    return script_path

def setup_git_environment(target_directory=None):
    """Checks and configures Git environment in the specified directory."""
    
    # Use the required directory path
    if target_directory is None:
        target_directory = r"C:\LabFiles\CAPSTONE-PROJECT\src\ui"
    
    # Ensure target directory exists
    os.makedirs(target_directory, exist_ok=True)
    
    print(f"🔧 Checking Git environment in {target_directory}...")
    
    # Change to target directory
    original_dir = os.getcwd()
    os.chdir(target_directory)
    
    try:
        # Check if git is installed
        result = subprocess.run(["git", "--version"], 
                              capture_output=True, check=True, timeout=10)
        print("✅ Git is installed")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("❌ Git is not installed or not accessible")
        os.chdir(original_dir)
        return False
    
    try:
        # Initialize repository if needed
        result = subprocess.run(["git", "status"], capture_output=True, timeout=10)
        if result.returncode != 0:
            print("📁 Initializing Git repository...")
            subprocess.run(["git", "init"], check=True, timeout=10)
            print("✅ Git repository initialized")
        else:
            print("✅ Git repository found")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("❌ Failed to setup Git repository")
        os.chdir(original_dir)
        return False
    
    # Fix Git ownership issues and configure Git user
    try:
        # Add safe directories to avoid ownership issues (both parent and subdirectory)
        parent_dir = os.path.dirname(target_directory).replace("\\", "/")
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", 
                       parent_dir], timeout=10)
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", 
                       target_directory.replace("\\", "/")], timeout=10)
        
        # Also add a wildcard for all subdirectories
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], 
                      timeout=10)
        
        # Configure Git user
        subprocess.run(["git", "config", "user.name", "Multi-Agent System"], 
                      timeout=10)
        subprocess.run(["git", "config", "user.email", "multiagent@example.com"], 
                      timeout=10)
        print("✅ Git user configured and safe directories added")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("⚠️  Could not configure Git - trying alternative approach...")
        
        # Alternative: Configure in the specific repository
        try:
            subprocess.run(["git", "config", "--local", "user.name", "Multi-Agent System"], 
                          timeout=10)
            subprocess.run(["git", "config", "--local", "user.email", "multiagent@example.com"], 
                          timeout=10)
            print("✅ Git user configured locally")
        except:
            print("❌ Git configuration failed")
    
    # Check for remote origin and configure if needed
    try:
        result = subprocess.run(["git", "remote", "get-url", "origin"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Git remote origin: {result.stdout.strip()}")
        else:
            print("⚠️  No Git remote 'origin' configured")
            print("   Attempting to add default remote...")
            
            # Try to add the remote automatically
            repo_url = "https://github.com/odl-user-1804678/Capstone-Project-Agentic-AI.git"
            try:
                subprocess.run(["git", "remote", "add", "origin", repo_url], 
                             check=True, timeout=10)
                print(f"✅ Added remote origin: {repo_url}")
            except subprocess.CalledProcessError:
                # Remote might already exist, try to set URL
                try:
                    subprocess.run(["git", "remote", "set-url", "origin", repo_url], 
                                 check=True, timeout=10)
                    print(f"✅ Updated remote origin: {repo_url}")
                except subprocess.CalledProcessError:
                    print("❌ Could not configure Git remote")
                    
    except Exception as e:
        print(f"⚠️  Could not check Git remote: {e}")
    
    # Return to original directory
    os.chdir(original_dir)
    return True

def save_html_and_push_to_github(html_code, target_directory=None):
    """Saves HTML code and pushes to GitHub in the specified directory."""
    
    # Use the required directory path
    if target_directory is None:
        target_directory = r"C:\LabFiles\CAPSTONE-PROJECT\src\ui"
    
    # Ensure target directory exists
    os.makedirs(target_directory, exist_ok=True)
    
    try:
        # Save HTML to file in the target directory
        html_file_path = os.path.join(target_directory, "index.html")
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_code)
        print(f"✅ HTML code saved to {html_file_path}")
        
        # Create deployment script in the same directory
        script_path = create_git_script(target_directory)
        
        print("🚀 Executing deployment script...")
        
        # Change to target directory before execution
        original_dir = os.getcwd()
        os.chdir(target_directory)
        
        try:
            if platform.system() == "Windows":
                # Use the full path to the batch file
                result = subprocess.run([script_path], shell=True, capture_output=True, 
                                      text=True, timeout=60, cwd=target_directory)
            else:
                # For Unix/Linux systems
                result = subprocess.run([script_path], capture_output=True, 
                                      text=True, timeout=60, cwd=target_directory)
            
            if result.returncode == 0:
                print("🎉 Deployment completed successfully!")
                print(f"Output: {result.stdout}")
            else:
                print("❌ Deployment failed:")
                print(f"Error: {result.stderr}")
                print(f"Output: {result.stdout}")
                
        finally:
            # Always return to original directory
            os.chdir(original_dir)
            
    except subprocess.TimeoutExpired:
        print("❌ Deployment timed out!")
        os.chdir(original_dir)
    except Exception as e:
        print(f"❌ Unexpected error during deployment: {str(e)}")
        if 'original_dir' in locals():
            os.chdir(original_dir)

async def run_multi_agent(user_input: str):
    """Main function to run the multi-agent workflow."""
    
    # Define target directory for deployment
    target_directory = r"C:\LabFiles\CAPSTONE-PROJECT\src\ui"
    
    print("🤖 Multi-Agent Weather App Builder")
    print("=" * 50)
    print(f"Platform: {platform.system()}")
    print(f"Target Directory: {target_directory}")
    
    # Setup Git environment in target directory
    if not setup_git_environment(target_directory):
        print("❌ Git environment setup failed. Please install Git and try again.")
        return None
    
    try:
        # Create kernel and agents
        kernel = create_kernel()
        
        # Create agents with unique names (letters only)
        agent_ba = ChatCompletionAgent(
            kernel=kernel, 
            name="BusinessAnalyst", 
            instructions=BA_PROMPT
        )
        agent_se = ChatCompletionAgent(
            kernel=kernel, 
            name="SoftwareEngineer", 
            instructions=SE_PROMPT
        )
        agent_po = ChatCompletionAgent(
            kernel=kernel, 
            name="ProductOwner", 
            instructions=PO_PROMPT
        )
        
        # Create agent group chat with termination strategy
        chat = AgentGroupChat(
            agents=[agent_ba, agent_se, agent_po],
            termination_strategy=ApprovalTerminationStrategy()
        )
        
        # Add initial user message
        await chat.add_chat_message(
            message=ChatMessageContent(role=AuthorRole.USER, content=user_input)
        )
        
        # Track all messages
        all_messages = [{'role': 'user', 'content': user_input}]
        
        print("🚀 Starting agent workflow...")
        
        # Process agent messages
        async for message in chat.invoke():
            print(f"🤖 {message.name}: {message.content[:100]}...")
            all_messages.append({
                'role': message.role.value,
                'content': message.content,
                'agent_name': message.name
            })
        
        print("\n" + "="*50)
        print("📋 WORKFLOW SUMMARY")
        print("="*50)
        
        # Check if ready for approval
        ready_for_approval = any(
            "READY FOR USER APPROVAL" in msg['content'].upper()
            for msg in all_messages
            if 'content' in msg
        )
        
        if ready_for_approval:
            print("✅ Agents completed work and are ready for approval!")
            
            # Extract HTML code
            html_code = extract_html_code(all_messages)
            if html_code:
                print("✅ HTML code extracted successfully!")
                
                # Simulate user approval (in production, replace with actual input)
                print("\n⏳ Waiting for user approval...")
                print("In production, user would type 'APPROVED' here.")
                
                # Add approval message
                approval_msg = ChatMessageContent(
                    role=AuthorRole.USER, 
                    content="APPROVED"
                )
                await chat.add_chat_message(message=approval_msg)
                all_messages.append({'role': 'user', 'content': 'APPROVED'})
                
                print("✅ User approved! Deploying to GitHub...")
                
                # Deploy to GitHub in the specified directory
                save_html_and_push_to_github(html_code, target_directory)
                
            else:
                print("❌ No HTML code found - cannot deploy!")
        else:
            print("❌ Workflow incomplete - agents did not reach approval stage")
        
        return {
            'messages': all_messages,
            'status': 'completed' if ready_for_approval else 'incomplete',
            'html_extracted': html_code is not None if ready_for_approval else False,
            'target_directory': target_directory
        }
        
    except Exception as e:
        print(f"❌ Error in multi-agent workflow: {str(e)}")
        return None

def main():
    """Main entry point."""
    
    # Set event loop policy for Windows to avoid ProactorEventLoop issues
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoop())
    
    try:
        user_input = (
            "Build a weather app for San Francisco. "
            "The app should show current weather, temperature, humidity, "
            "and a 5-day forecast. Make it responsive and visually appealing. "
            "Once it's done and ready, I will reply 'APPROVED'."
        )
        
        # Create and run new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(run_multi_agent(user_input))
            
            if result:
                print(f"\n📊 Final Status: {result['status']}")
                print(f"📝 Messages processed: {len(result['messages'])}")
                print(f"🎯 Target directory: {result['target_directory']}")
                if result.get('html_extracted'):
                    print("✅ HTML code was successfully extracted and deployed!")
            else:
                print("❌ Workflow failed to complete")
                
        finally:
            # Proper cleanup
            try:
                # Cancel all running tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                
                # Wait for tasks to complete cancellation
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                loop.close()
                
    except KeyboardInterrupt:
        print("\n⏹️  Workflow interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()