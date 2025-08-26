# 🌟 **Google Gemini AI Setup Guide**

## 🎯 **Why Choose Gemini for Code Reviews?**

Google Gemini offers excellent value for AI-powered code analysis:

✅ **FREE Tier Available** - Start without any cost  
✅ **Competitive Pricing** - ~$0.0015 per 1K tokens (Gemini 1.5 Flash)  
✅ **Advanced Models** - Gemini 1.5 Pro with 2M token context  
✅ **Fast Performance** - Gemini 1.5 Flash for quick analysis  
✅ **Google Quality** - Built by Google's AI research team  

---

## 🚀 **Quick Setup Steps**

### **Step 1: Get Your Gemini API Key**

1. **Go to Google AI Studio**: https://aistudio.google.com/app/apikey
2. **Sign in** with your Google account
3. **Click "Create API Key"**
4. **Choose option**:
   - "Create API key in new project" (recommended for new users)
   - Or select an existing Google Cloud project
5. **Copy the API key** (starts with `AIza`)
6. **Keep it secure** - you'll need it for configuration

### **Step 2: Configure in PerfectMCP**

1. **Open admin interface**: http://192.168.0.78:8080
2. **Navigate to "Code Analysis"** page
3. **Click "AI Settings" tab**
4. **Select "Google Gemini"** as provider
5. **Choose your model**:
   - **Gemini 1.5 Pro** (best quality, slower)
   - **Gemini 1.5 Flash** (faster, good quality)
6. **Enter your API key** (the one starting with `AIza`)
7. **Click "Test Connection"** to verify
8. **Click "Save Settings"** to apply

---

## 🎛️ **Gemini Model Options**

### **Gemini 1.5 Pro (Recommended)**
- **Best for**: Comprehensive code analysis
- **Context**: Up to 2M tokens (huge files!)
- **Quality**: Highest accuracy and detail
- **Speed**: Moderate (2-5 seconds)
- **Cost**: ~$0.0035 per 1K input tokens

### **Gemini 1.5 Flash (Fast)**
- **Best for**: Quick code reviews
- **Context**: Up to 1M tokens
- **Quality**: Very good, optimized for speed
- **Speed**: Fast (1-2 seconds)
- **Cost**: ~$0.0015 per 1K input tokens

### **Gemini 1.0 Pro (Legacy)**
- **Best for**: Basic analysis
- **Context**: 32K tokens
- **Quality**: Good for simple tasks
- **Speed**: Fast
- **Cost**: Lower cost option

---

## 💰 **Pricing & Free Tier**

### **FREE Tier Benefits**
- **15 requests per minute**
- **1 million tokens per day**
- **Perfect for personal projects**
- **No credit card required**

### **Paid Tier (Pay-as-you-go)**
- **Higher rate limits**
- **Unlimited daily usage**
- **Enterprise support**
- **Starting at $0.0015 per 1K tokens**

### **Cost Comparison**
| Provider | Model | Cost per 1K tokens |
|----------|-------|-------------------|
| **Gemini** | 1.5 Flash | **$0.0015** ⭐ |
| **Gemini** | 1.5 Pro | $0.0035 |
| OpenAI | GPT-3.5 | $0.002 |
| OpenAI | GPT-4 | $0.03 |
| Anthropic | Claude 3 | $0.015 |

**🎉 Gemini 1.5 Flash is the most cost-effective option!**

---

## 🔧 **Configuration Examples**

### **For Personal Projects (FREE)**
```yaml
ai_model:
  provider: "gemini"
  model: "gemini-1.5-flash"
  api_key: "AIza..."
  max_tokens: 1000
  temperature: 0.1
```

### **For Professional Use**
```yaml
ai_model:
  provider: "gemini"
  model: "gemini-1.5-pro"
  api_key: "AIza..."
  max_tokens: 2000
  temperature: 0.1
```

### **For High-Volume Analysis**
```yaml
ai_model:
  provider: "gemini"
  model: "gemini-1.5-flash"
  api_key: "AIza..."
  max_tokens: 1500
  temperature: 0.05
```

---

## 🧪 **Testing Your Setup**

### **1. Connection Test**
- Go to AI Settings tab
- Click "Test Connection"
- Should see: ✅ "Connection successful"

### **2. Sample Code Analysis**
Try analyzing this Python code:
```python
def calculate_total(items):
    total = 0
    for item in items:
        total = total + item['price']
    return total
```

**Expected Gemini Response:**
```
🔍 Code Analysis:

✅ Strengths:
- Clear function name and purpose
- Simple, readable logic

⚠️ Suggestions:
1. Use sum() with generator for better performance
2. Add type hints for better code clarity
3. Add docstring to explain function
4. Consider error handling for missing 'price' key

🚀 Improved version:
def calculate_total(items: List[Dict[str, float]]) -> float:
    """Calculate total price from list of items."""
    return sum(item['price'] for item in items)
```

---

## 🔒 **Security & Privacy**

### **API Key Security**
- ✅ Keys are encrypted in PerfectMCP
- ✅ Never logged or exposed
- ✅ Stored securely in config files
- ✅ Can be changed anytime

### **Code Privacy with Gemini**
- ⚠️ Code is sent to Google for analysis
- ✅ Google doesn't use data for training (per policy)
- ✅ Data is processed securely
- ✅ No permanent storage of your code

### **Best Practices**
- 🔐 Don't include sensitive data in code analysis
- 🔐 Use environment variables for secrets
- 🔐 Review Google's privacy policy
- 🔐 Rotate API keys periodically

---

## 🛠️ **Troubleshooting**

### **Common Issues**

#### **"Invalid API Key" Error**
- ✅ Check key starts with `AIza`
- ✅ Regenerate key from Google AI Studio
- ✅ Ensure no extra spaces

#### **"Model Not Found" Error**
- ✅ Use exact model names: `gemini-1.5-pro`, `gemini-1.5-flash`
- ✅ Check model availability in your region

#### **"Rate Limit" Error**
- ✅ Wait a minute and try again
- ✅ Upgrade to paid tier for higher limits
- ✅ Use Gemini 1.5 Flash for faster processing

#### **"Connection Failed" Error**
- ✅ Check internet connectivity
- ✅ Verify API key is active
- ✅ Try different model

### **Getting Help**
- Check Google AI Studio documentation
- Review API usage in Google Cloud Console
- Test with simple code snippets first

---

## 🎉 **You're Ready with Gemini!**

Once configured, Gemini will provide:

✅ **Fast code analysis** (1-2 seconds with Flash)  
✅ **Detailed suggestions** with explanations  
✅ **Cost-effective reviews** (lowest cost option)  
✅ **Large context support** (up to 2M tokens)  
✅ **Multi-language support** (Python, JS, Java, etc.)  

### **Next Steps:**
1. ✅ Get your API key from Google AI Studio
2. ✅ Configure in PerfectMCP AI Settings
3. ✅ Test with sample code
4. ✅ Start analyzing your projects!

### **Pro Tips:**
- 🚀 Use **Gemini 1.5 Flash** for daily development
- 🎯 Use **Gemini 1.5 Pro** for critical code reviews
- 💰 Start with **FREE tier** to test functionality
- 📊 Monitor usage in Google Cloud Console

**Happy coding with Gemini AI! 🌟**
