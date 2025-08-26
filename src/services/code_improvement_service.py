"""
Code Improvement Service for PerfectMCP
Handles code analysis, suggestions, and quality metrics
"""

import ast
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import pylint.lint
from pylint.reporters.text import TextReporter
from io import StringIO

from utils.database import DatabaseManager
from utils.config import CodeImprovementConfig
from utils.logger import LoggerMixin


class CodeImprovementService(LoggerMixin):
    """Service for code analysis and improvement suggestions"""
    
    def __init__(self, db_manager: DatabaseManager, config: CodeImprovementConfig):
        self.db = db_manager
        self.config = config
        self._ai_client = None
        
    async def initialize(self):
        """Initialize the code improvement service"""
        self.logger.info("Initializing Code Improvement Service")
        
        # Initialize AI client based on configuration
        await self._init_ai_client()
        
        self.logger.info("Code Improvement Service initialized successfully")
    
    async def _init_ai_client(self):
        """Initialize AI client for code suggestions"""
        try:
            if self.config.ai_model.provider.lower() == "openai":
                import openai
                # Note: In production, use environment variables for API keys
                # self._ai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self.logger.info("OpenAI client initialized (API key required)")
            elif self.config.ai_model.provider.lower() == "anthropic":
                import anthropic
                # self._ai_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                self.logger.info("Anthropic client initialized (API key required)")
            else:
                self.logger.warning(f"Unknown AI provider: {self.config.ai_model.provider}")
        except ImportError as e:
            self.logger.warning(f"AI client not available: {e}")
    
    async def analyze_code(self, session_id: str, code: str, language: str, 
                          file_path: Optional[str] = None) -> Dict[str, Any]:
        """Analyze code and return detailed analysis"""
        if len(code.encode('utf-8')) > self.config.analysis.max_file_size:
            raise ValueError("Code file too large")
        
        if language not in self.config.analysis.supported_languages:
            raise ValueError(f"Language {language} not supported")
        
        analysis_result = {
            "session_id": session_id,
            "language": language,
            "file_path": file_path,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {},
            "issues": [],
            "suggestions": [],
            "complexity": {}
        }
        
        try:
            if language == "python":
                analysis_result.update(await self._analyze_python_code(code))
            elif language in ["javascript", "typescript"]:
                analysis_result.update(await self._analyze_js_code(code, language))
            else:
                analysis_result.update(await self._analyze_generic_code(code, language))
            
            # Store analysis in database
            await self._store_analysis(session_id, analysis_result)
            
            self.logger.info(f"Analyzed {language} code for session {session_id}")
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Code analysis failed: {e}")
            raise
    
    async def suggest_improvements(self, session_id: str, code: str, language: str,
                                 file_path: Optional[str] = None) -> Dict[str, Any]:
        """Generate improvement suggestions for code"""
        # First analyze the code
        analysis = await self.analyze_code(session_id, code, language, file_path)
        
        # Generate AI-powered suggestions if available
        ai_suggestions = []
        if self._ai_client:
            ai_suggestions = await self._get_ai_suggestions(code, language, analysis)
        
        # Combine with rule-based suggestions
        rule_suggestions = await self._get_rule_based_suggestions(code, language, analysis)
        
        suggestions = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "ai_suggestions": ai_suggestions,
            "rule_suggestions": rule_suggestions,
            "priority_suggestions": self._prioritize_suggestions(ai_suggestions + rule_suggestions),
            "analysis_summary": {
                "total_issues": len(analysis.get("issues", [])),
                "complexity_score": analysis.get("complexity", {}).get("cyclomatic", 0),
                "maintainability_score": self._calculate_maintainability_score(analysis)
            }
        }
        
        # Store suggestions
        await self._store_suggestions(session_id, suggestions)
        
        return suggestions
    
    async def get_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get code quality metrics for a session"""
        collection = self.db.get_collection_name("improvements")
        
        # Get recent analyses
        analyses = await self.db.mongo_find_many(
            collection,
            {"session_id": session_id, "type": "analysis"},
            limit=10,
            sort=[("timestamp", -1)]
        )
        
        if not analyses:
            return {"session_id": session_id, "metrics": {}, "trend": {}}
        
        # Calculate aggregate metrics
        metrics = self._calculate_aggregate_metrics(analyses)
        
        return {
            "session_id": session_id,
            "metrics": metrics,
            "trend": self._calculate_trend(analyses),
            "last_updated": analyses[0]["timestamp"] if analyses else None
        }
    
    async def get_improvement_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get improvement history for a session"""
        collection = self.db.get_collection_name("improvements")
        
        history = await self.db.mongo_find_many(
            collection,
            {"session_id": session_id},
            limit=limit,
            sort=[("timestamp", -1)]
        )
        
        return history
    
    async def _analyze_python_code(self, code: str) -> Dict[str, Any]:
        """Analyze Python code specifically"""
        result = {
            "metrics": {},
            "issues": [],
            "complexity": {}
        }
        
        try:
            # Parse AST
            tree = ast.parse(code)
            
            # Basic metrics
            result["metrics"] = {
                "lines_of_code": len(code.splitlines()),
                "functions": len([node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]),
                "classes": len([node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]),
                "imports": len([node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))])
            }
            
            # Complexity analysis
            result["complexity"] = await self._calculate_python_complexity(tree)
            
            # Run pylint analysis
            pylint_issues = await self._run_pylint_analysis(code)
            result["issues"].extend(pylint_issues)
            
        except SyntaxError as e:
            result["issues"].append({
                "type": "syntax_error",
                "message": str(e),
                "line": e.lineno,
                "severity": "error"
            })
        except Exception as e:
            self.logger.error(f"Python analysis error: {e}")
            result["issues"].append({
                "type": "analysis_error",
                "message": f"Analysis failed: {str(e)}",
                "severity": "warning"
            })
        
        return result
    
    async def _analyze_js_code(self, code: str, language: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript code"""
        result = {
            "metrics": {
                "lines_of_code": len(code.splitlines()),
                "functions": len(re.findall(r'function\s+\w+|=>\s*{|\w+\s*:\s*function', code)),
                "classes": len(re.findall(r'class\s+\w+', code)),
                "imports": len(re.findall(r'import\s+.*from|require\s*\(', code))
            },
            "issues": [],
            "complexity": {"cyclomatic": self._estimate_js_complexity(code)}
        }
        
        # Basic linting rules
        issues = []
        
        # Check for common issues
        if 'var ' in code:
            issues.append({
                "type": "style",
                "message": "Consider using 'let' or 'const' instead of 'var'",
                "severity": "info"
            })
        
        if '==' in code and '===' not in code:
            issues.append({
                "type": "style",
                "message": "Consider using strict equality (===) instead of loose equality (==)",
                "severity": "warning"
            })
        
        result["issues"] = issues
        return result
    
    async def _analyze_generic_code(self, code: str, language: str) -> Dict[str, Any]:
        """Generic code analysis for unsupported languages"""
        return {
            "metrics": {
                "lines_of_code": len(code.splitlines()),
                "characters": len(code),
                "blank_lines": len([line for line in code.splitlines() if not line.strip()])
            },
            "issues": [],
            "complexity": {"estimated": min(len(code.splitlines()) // 10, 10)}
        }
    
    async def _calculate_python_complexity(self, tree: ast.AST) -> Dict[str, Any]:
        """Calculate complexity metrics for Python code"""
        complexity = {"cyclomatic": 1}  # Base complexity
        
        # Count decision points
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity["cyclomatic"] += 1
            elif isinstance(node, ast.BoolOp):
                complexity["cyclomatic"] += len(node.values) - 1
        
        return complexity
    
    def _estimate_js_complexity(self, code: str) -> int:
        """Estimate cyclomatic complexity for JavaScript"""
        complexity = 1
        
        # Count decision points
        patterns = [
            r'\bif\s*\(',
            r'\bwhile\s*\(',
            r'\bfor\s*\(',
            r'\btry\s*{',
            r'\bcatch\s*\(',
            r'\?\s*.*\s*:',  # ternary operator
            r'&&|\|\|'  # logical operators
        ]
        
        for pattern in patterns:
            complexity += len(re.findall(pattern, code))
        
        return complexity
    
    async def _run_pylint_analysis(self, code: str) -> List[Dict[str, Any]]:
        """Run pylint analysis on Python code"""
        issues = []
        
        try:
            # Create a temporary file-like object
            output = StringIO()
            reporter = TextReporter(output)
            
            # Run pylint
            pylint.lint.Run(['-'], reporter=reporter, exit=False)
            
            # Parse output (simplified)
            output_lines = output.getvalue().splitlines()
            for line in output_lines:
                if ':' in line and any(severity in line for severity in ['E:', 'W:', 'C:', 'R:']):
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        issues.append({
                            "type": "pylint",
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "message": parts[3].strip(),
                            "severity": "error" if parts[2].startswith('E') else "warning"
                        })
        
        except Exception as e:
            self.logger.debug(f"Pylint analysis failed: {e}")
        
        return issues
    
    async def _get_ai_suggestions(self, code: str, language: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get AI-powered improvement suggestions"""
        if not self._ai_client:
            return []
        
        try:
            prompt = self._build_ai_prompt(code, language, analysis)
            
            # This would be the actual AI call - placeholder for now
            # response = await self._ai_client.chat.completions.create(...)
            
            # Mock response for demonstration
            return [
                {
                    "type": "ai_suggestion",
                    "category": "performance",
                    "message": "Consider using list comprehension for better performance",
                    "confidence": 0.8,
                    "line_range": [5, 10]
                }
            ]
        
        except Exception as e:
            self.logger.error(f"AI suggestion generation failed: {e}")
            return []
    
    async def _get_rule_based_suggestions(self, code: str, language: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get rule-based improvement suggestions"""
        suggestions = []
        
        # High complexity warning
        complexity = analysis.get("complexity", {}).get("cyclomatic", 0)
        if complexity > 10:
            suggestions.append({
                "type": "complexity",
                "category": "maintainability",
                "message": f"High cyclomatic complexity ({complexity}). Consider breaking down into smaller functions.",
                "severity": "warning",
                "priority": "high"
            })
        
        # Too many lines warning
        lines = analysis.get("metrics", {}).get("lines_of_code", 0)
        if lines > 100:
            suggestions.append({
                "type": "length",
                "category": "maintainability",
                "message": f"Function/file is quite long ({lines} lines). Consider splitting into smaller units.",
                "severity": "info",
                "priority": "medium"
            })
        
        return suggestions
    
    def _prioritize_suggestions(self, suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize suggestions by importance"""
        priority_order = {"high": 3, "medium": 2, "low": 1}
        
        return sorted(
            suggestions,
            key=lambda x: priority_order.get(x.get("priority", "low"), 1),
            reverse=True
        )
    
    def _calculate_maintainability_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate a maintainability score (0-100)"""
        score = 100.0
        
        # Deduct for complexity
        complexity = analysis.get("complexity", {}).get("cyclomatic", 0)
        score -= min(complexity * 2, 30)
        
        # Deduct for issues
        issues = len(analysis.get("issues", []))
        score -= min(issues * 5, 40)
        
        # Deduct for length
        lines = analysis.get("metrics", {}).get("lines_of_code", 0)
        if lines > 100:
            score -= min((lines - 100) * 0.1, 20)
        
        return max(score, 0)
    
    def _calculate_aggregate_metrics(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate metrics from multiple analyses"""
        if not analyses:
            return {}
        
        total_lines = sum(a.get("metrics", {}).get("lines_of_code", 0) for a in analyses)
        total_issues = sum(len(a.get("issues", [])) for a in analyses)
        avg_complexity = sum(a.get("complexity", {}).get("cyclomatic", 0) for a in analyses) / len(analyses)
        
        return {
            "total_lines_analyzed": total_lines,
            "total_issues_found": total_issues,
            "average_complexity": round(avg_complexity, 2),
            "analyses_count": len(analyses)
        }
    
    def _calculate_trend(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate improvement trends"""
        if len(analyses) < 2:
            return {"trend": "insufficient_data"}
        
        recent = analyses[:len(analyses)//2]
        older = analyses[len(analyses)//2:]
        
        recent_avg_issues = sum(len(a.get("issues", [])) for a in recent) / len(recent)
        older_avg_issues = sum(len(a.get("issues", [])) for a in older) / len(older)
        
        if recent_avg_issues < older_avg_issues:
            trend = "improving"
        elif recent_avg_issues > older_avg_issues:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "recent_avg_issues": round(recent_avg_issues, 2),
            "older_avg_issues": round(older_avg_issues, 2)
        }
    
    def _build_ai_prompt(self, code: str, language: str, analysis: Dict[str, Any]) -> str:
        """Build prompt for AI suggestions"""
        return f"""
        Analyze this {language} code and provide improvement suggestions:
        
        Code:
        ```{language}
        {code}
        ```
        
        Current analysis shows:
        - Complexity: {analysis.get('complexity', {})}
        - Issues found: {len(analysis.get('issues', []))}
        - Metrics: {analysis.get('metrics', {})}
        
        Please provide specific, actionable suggestions for improvement.
        """
    
    async def _store_analysis(self, session_id: str, analysis: Dict[str, Any]):
        """Store analysis results in database"""
        analysis["type"] = "analysis"
        collection = self.db.get_collection_name("improvements")
        await self.db.mongo_insert_one(collection, analysis)
    
    async def _store_suggestions(self, session_id: str, suggestions: Dict[str, Any]):
        """Store suggestions in database"""
        suggestions["type"] = "suggestions"
        collection = self.db.get_collection_name("improvements")
        await self.db.mongo_insert_one(collection, suggestions)
