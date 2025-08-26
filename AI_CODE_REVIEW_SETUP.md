# 🤖 **AI Code Review Configuration Guide**

## 🎯 **How to Configure AI for Code Reviews**

The PerfectMCP Admin Server now includes a comprehensive AI configuration interface for code reviews. Here's how to set it up:

---

## 🚀 **Quick Setup Steps**

### **1. Access the Configuration Interface**
1. Open your admin interface: `http://192.168.0.78:8080`
2. Navigate to **Code Analysis** page
3. Click on the **"AI Settings"** tab

### **2. Choose Your AI Provider & Enter API Key**

#### **Step-by-Step Configuration:**

1. **Select Provider**: Choose from OpenAI, Anthropic, Google Gemini, or Custom API
2. **Enter API Key**: The system will automatically load available models
3. **Select Model**: Choose from your account's available models
4. **Test & Save**: Verify connection and save settings

#### **Option A: OpenAI (Recommended)**
- **Provider**: Select "OpenAI (GPT-4, GPT-3.5)"
- **API Key**: Enter your OpenAI API key (starts with `sk-`)
- **Get API Key**: https://platform.openai.com/api-keys
- **Models**: System will load your available models (GPT-4, GPT-3.5, etc.)

#### **Option B: Anthropic (Claude)**
- **Provider**: Select "Anthropic (Claude)"
- **API Key**: Enter your Anthropic API key (starts with `sk-ant-`)
- **Get API Key**: https://console.anthropic.com/
- **Models**: Claude 3.5 Sonnet, Claude 3 Sonnet, Claude 3 Haiku, etc.

#### **Option C: Google Gemini (NEW!)**
- **Provider**: Select "Google Gemini"
- **API Key**: Enter your Google AI Studio API key (starts with `AIza`)
- **Get API Key**: https://aistudio.google.com/app/apikey
- **Models**: System will load available Gemini models from your account

#### **Option D: Custom API**
- **Provider**: Select "Custom API"
- **API Key**: Enter your API key
- **API Base URL**: Enter your custom API endpoint (e.g., `https://api.example.com/v1`)
- **Models**: System will attempt to load models from your custom endpoint

### **3. Dynamic Model Loading (NEW!)**

**🎉 Smart Model Detection:**
- **Enter API Key** → System automatically loads your available models
- **Real-time Updates** → Models refresh when you change providers
- **Account-specific** → Only shows models you have access to
- **Recommended Models** → Highlighted with ⭐ for best results

**How it works:**
1. Select your AI provider
2. Enter your API key
3. **Models load automatically** - no guessing!
4. Choose from your actual available models
5. Recommended models are marked with ⭐

### **4. Configure Analysis Settings**
- **Max Tokens**: 2000 (recommended for detailed analysis)
- **Temperature**: 0.1 (focused responses) to 1.0 (creative responses)
- **Max File Size**: 1MB (adjust based on your needs)
- **Languages**: Select the programming languages you want to analyze

### **5. Test & Save**
1. Click **"Test Connection"** to verify your settings
2. Click **"Save Settings"** to apply the configuration

---

## 🔧 **Detailed Configuration Options**

### **AI Provider Settings**

| Setting | Description | Recommended Value |
|---------|-------------|-------------------|
| **Provider** | AI service provider | OpenAI (best quality) |
| **Model** | Specific AI model | GPT-4 (most capable) |
| **API Key** | Your authentication key | Get from provider |
| **API Base** | Custom endpoint (if needed) | Leave empty for standard |

### **Analysis Settings**

| Setting | Description | Recommended Value |
|---------|-------------|-------------------|
| **Max Tokens** | Response length limit | 2000 (detailed analysis) |
| **Temperature** | Response creativity | 0.1 (focused/consistent) |
| **Max File Size** | File size limit | 1MB (balance performance) |
| **Languages** | Supported languages | All (Python, JS, etc.) |

---

## 🔑 **Getting API Keys**

### **OpenAI API Key**
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. **Cost**: ~$0.03 per 1K tokens (GPT-4)

### **Anthropic API Key**
1. Go to https://console.anthropic.com/
2. Sign in or create an account
3. Navigate to "API Keys"
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-`)
6. **Cost**: ~$0.015 per 1K tokens (Claude 3 Sonnet)

### **Google Gemini API Key (NEW!)**
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Choose "Create API key in new project" or select existing project
5. Copy the key (starts with `AIza`)
6. **Cost**: FREE tier available! Then ~$0.0015 per 1K tokens (Gemini 1.5 Flash)

### **Custom API**
- Use any OpenAI-compatible API
- Examples: Azure OpenAI, local models, etc.
- Ensure the endpoint supports `/chat/completions`

---

## 🧪 **Testing Your Configuration**

### **Connection Test**
1. Enter your settings in the AI Settings tab
2. Click **"Test Connection"**
3. Look for success message: ✅ "Connection successful!"

### **Code Analysis Test**
1. Go to the "Analysis History" tab
2. Click **"Run Analysis"**
3. Upload a code file or paste code
4. Check if AI suggestions appear

---

## 🎯 **Usage Examples**

### **What the AI Will Analyze:**
- **Code Quality**: Complexity, readability, maintainability
- **Best Practices**: Naming conventions, structure, patterns
- **Performance**: Optimization opportunities
- **Security**: Potential vulnerabilities
- **Documentation**: Missing comments, docstrings
- **Testing**: Test coverage suggestions

### **Sample AI Response:**
```
🔍 Code Analysis Results:

✅ Strengths:
- Good error handling with try/catch blocks
- Clear variable naming conventions
- Proper function decomposition

⚠️ Suggestions:
1. Add type hints for better code clarity
2. Consider using list comprehension on line 15
3. Extract magic numbers into constants
4. Add docstring to main function

🚀 Performance:
- Current complexity: Medium (3.2/10)
- Suggested improvements could reduce to 2.1/10
```

---

## 🔒 **Security & Privacy**

### **API Key Security**
- ✅ Keys are encrypted and stored securely
- ✅ Keys are never logged or exposed
- ✅ Keys are only used for AI API calls
- ✅ You can change/remove keys anytime

### **Code Privacy**
- ⚠️ Code is sent to AI provider for analysis
- ⚠️ Check your provider's privacy policy
- ✅ No code is stored permanently
- ✅ Analysis results are stored locally

---

## 🛠️ **Troubleshooting**

### **Common Issues**

#### **"Connection Failed" Error**
- ✅ Check API key is correct and active
- ✅ Verify you have credits/quota remaining
- ✅ Ensure internet connectivity
- ✅ Check API base URL (for custom providers)

#### **"Invalid API Key" Error**
- ✅ Regenerate API key from provider
- ✅ Check for extra spaces or characters
- ✅ Verify key format (OpenAI: `sk-`, Anthropic: `sk-ant-`, Gemini: `AIza`)

#### **"Model Not Found" Error**
- ✅ Check model name spelling
- ✅ Verify model access permissions
- ✅ Try a different model (e.g., gpt-3.5-turbo)

#### **"Rate Limit" Error**
- ✅ Wait a few minutes and try again
- ✅ Check your API usage limits
- ✅ Consider upgrading your plan

### **Getting Help**
- Check the connection status in the AI Settings tab
- Look at the server logs: `journalctl -u pmpc.service -f`
- Test with a simple code snippet first

---

## 🎉 **You're Ready!**

Once configured, your AI code review system will:

✅ **Analyze code quality** automatically  
✅ **Provide improvement suggestions** with explanations  
✅ **Track metrics** over time  
✅ **Support multiple languages** (Python, JS, Java, etc.)  
✅ **Generate detailed reports** for your codebase  

**Next Steps:**
1. Configure your AI provider using the steps above
2. Test with a sample code file
3. Start analyzing your projects!

---

## 📞 **Support**

If you need help:
- Check the troubleshooting section above
- Review the connection test results
- Ensure your API key has sufficient credits
- Try with a different AI provider if issues persist

**Happy coding with AI-powered reviews!** 🚀
