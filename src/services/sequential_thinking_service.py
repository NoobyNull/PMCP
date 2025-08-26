"""
Sequential Thinking Service for PerfectMCP
Step-by-step reasoning, chain-of-thought processing, and logical problem decomposition
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from utils.database import DatabaseManager
from utils.logger import LoggerMixin


class ThinkingStep(Enum):
    """Types of thinking steps"""
    PROBLEM_ANALYSIS = "problem_analysis"
    HYPOTHESIS_FORMATION = "hypothesis_formation"
    EVIDENCE_GATHERING = "evidence_gathering"
    LOGICAL_REASONING = "logical_reasoning"
    SOLUTION_SYNTHESIS = "solution_synthesis"
    VALIDATION = "validation"
    REFLECTION = "reflection"


class ReasoningType(Enum):
    """Types of reasoning"""
    DEDUCTIVE = "deductive"      # General to specific
    INDUCTIVE = "inductive"      # Specific to general
    ABDUCTIVE = "abductive"      # Best explanation
    ANALOGICAL = "analogical"    # Similarity-based
    CAUSAL = "causal"           # Cause-effect
    SYSTEMATIC = "systematic"    # Step-by-step


class ConfidenceLevel(Enum):
    """Confidence levels for reasoning steps"""
    VERY_LOW = 0.1
    LOW = 0.3
    MEDIUM = 0.5
    HIGH = 0.7
    VERY_HIGH = 0.9


class SequentialThinkingService(LoggerMixin):
    """Service for step-by-step reasoning and logical problem decomposition"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._thinking_chains: Dict[str, List[Dict]] = {}
        self._reasoning_patterns: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize the Sequential Thinking service"""
        self.logger.info("Initializing Sequential Thinking Service")
        
        # Load existing thinking chains
        await self._load_thinking_chains()
        
        # Initialize reasoning patterns
        await self._initialize_reasoning_patterns()
        
        self.logger.info("Sequential Thinking Service initialized successfully")
    
    async def shutdown(self):
        """Shutdown the Sequential Thinking service"""
        # Save thinking chains
        await self._save_thinking_chains()
        self.logger.info("Sequential Thinking Service shutdown complete")
    
    async def start_thinking_chain(
        self, 
        session_id: str, 
        problem: str,
        reasoning_type: ReasoningType = ReasoningType.SYSTEMATIC,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start a new chain of thought for a problem"""
        
        chain_id = str(uuid.uuid4())
        
        initial_step = {
            "step_id": str(uuid.uuid4()),
            "step_type": ThinkingStep.PROBLEM_ANALYSIS.value,
            "content": f"Problem to solve: {problem}",
            "reasoning_type": reasoning_type.value,
            "confidence": ConfidenceLevel.HIGH.value,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {},
            "dependencies": [],
            "outcomes": []
        }
        
        thinking_chain = {
            "chain_id": chain_id,
            "session_id": session_id,
            "problem": problem,
            "reasoning_type": reasoning_type.value,
            "status": "active",
            "steps": [initial_step],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Store in memory
        self._thinking_chains[chain_id] = thinking_chain
        
        # Store in database
        await self.db.mongo_insert_one("thinking_chains", thinking_chain)
        
        self.logger.info(f"Started thinking chain {chain_id}", 
                        session_id=session_id, problem=problem[:100])
        
        return chain_id
    
    async def add_thinking_step(
        self, 
        chain_id: str,
        step_type: ThinkingStep,
        content: str,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
        dependencies: Optional[List[str]] = None,
        evidence: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a step to an existing thinking chain"""
        
        if chain_id not in self._thinking_chains:
            raise ValueError(f"Thinking chain {chain_id} not found")
        
        step_id = str(uuid.uuid4())
        
        thinking_step = {
            "step_id": step_id,
            "step_type": step_type.value,
            "content": content,
            "confidence": confidence.value,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": dependencies or [],
            "evidence": evidence or {},
            "outcomes": [],
            "validated": False
        }
        
        # Add to chain
        self._thinking_chains[chain_id]["steps"].append(thinking_step)
        self._thinking_chains[chain_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # Update database
        await self.db.mongo_update_one(
            "thinking_chains",
            {"chain_id": chain_id},
            {
                "steps": self._thinking_chains[chain_id]["steps"],
                "updated_at": datetime.utcnow().isoformat()
            }
        )
        
        self.logger.debug(f"Added thinking step {step_id} to chain {chain_id}")
        
        return step_id
    
    async def validate_step(
        self, 
        chain_id: str, 
        step_id: str,
        validation_result: bool,
        validation_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate a thinking step"""
        
        if chain_id not in self._thinking_chains:
            raise ValueError(f"Thinking chain {chain_id} not found")
        
        chain = self._thinking_chains[chain_id]
        step = None
        
        for s in chain["steps"]:
            if s["step_id"] == step_id:
                step = s
                break
        
        if not step:
            raise ValueError(f"Step {step_id} not found in chain {chain_id}")
        
        # Update step validation
        step["validated"] = validation_result
        step["validation_notes"] = validation_notes
        step["validation_timestamp"] = datetime.utcnow().isoformat()
        
        # Adjust confidence based on validation
        if validation_result:
            step["confidence"] = min(1.0, step["confidence"] * 1.2)
        else:
            step["confidence"] = max(0.1, step["confidence"] * 0.8)
        
        # Update database
        await self.db.mongo_update_one(
            "thinking_chains",
            {"chain_id": chain_id},
            {"steps": chain["steps"]}
        )
        
        return {
            "step_id": step_id,
            "validated": validation_result,
            "new_confidence": step["confidence"],
            "notes": validation_notes
        }
    
    async def synthesize_solution(self, chain_id: str) -> Dict[str, Any]:
        """Synthesize a solution from the thinking chain"""
        
        if chain_id not in self._thinking_chains:
            raise ValueError(f"Thinking chain {chain_id} not found")
        
        chain = self._thinking_chains[chain_id]
        steps = chain["steps"]
        
        # Analyze the chain
        analysis = await self._analyze_thinking_chain(chain)
        
        # Generate solution synthesis
        solution_step = await self.add_thinking_step(
            chain_id=chain_id,
            step_type=ThinkingStep.SOLUTION_SYNTHESIS,
            content=f"Synthesized solution based on {len(steps)} thinking steps",
            confidence=ConfidenceLevel.HIGH,
            evidence=analysis
        )
        
        # Create solution summary
        solution = {
            "chain_id": chain_id,
            "solution_step_id": solution_step,
            "problem": chain["problem"],
            "reasoning_type": chain["reasoning_type"],
            "total_steps": len(steps),
            "confidence_score": analysis["average_confidence"],
            "logical_consistency": analysis["logical_consistency"],
            "evidence_strength": analysis["evidence_strength"],
            "solution_summary": await self._generate_solution_summary(chain),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store solution
        await self.db.mongo_insert_one("solutions", solution)
        
        # Mark chain as completed
        self._thinking_chains[chain_id]["status"] = "completed"
        await self.db.mongo_update_one(
            "thinking_chains",
            {"chain_id": chain_id},
            {"status": "completed"}
        )
        
        return solution
    
    async def branch_thinking(
        self, 
        chain_id: str, 
        step_id: str,
        alternative_content: str,
        reasoning_type: Optional[ReasoningType] = None
    ) -> str:
        """Create a branch in thinking from a specific step"""
        
        if chain_id not in self._thinking_chains:
            raise ValueError(f"Thinking chain {chain_id} not found")
        
        original_chain = self._thinking_chains[chain_id]
        
        # Find the branching point
        branch_point_index = -1
        for i, step in enumerate(original_chain["steps"]):
            if step["step_id"] == step_id:
                branch_point_index = i
                break
        
        if branch_point_index == -1:
            raise ValueError(f"Step {step_id} not found")
        
        # Create new branch chain
        branch_chain_id = str(uuid.uuid4())
        
        # Copy steps up to branch point
        branch_steps = original_chain["steps"][:branch_point_index + 1].copy()
        
        # Add alternative step
        alternative_step = {
            "step_id": str(uuid.uuid4()),
            "step_type": ThinkingStep.HYPOTHESIS_FORMATION.value,
            "content": alternative_content,
            "confidence": ConfidenceLevel.MEDIUM.value,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": [step_id],
            "evidence": {},
            "outcomes": [],
            "validated": False,
            "branch_from": step_id
        }
        
        branch_steps.append(alternative_step)
        
        branch_chain = {
            "chain_id": branch_chain_id,
            "session_id": original_chain["session_id"],
            "problem": original_chain["problem"],
            "reasoning_type": reasoning_type.value if reasoning_type else original_chain["reasoning_type"],
            "status": "active",
            "steps": branch_steps,
            "parent_chain": chain_id,
            "branch_point": step_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Store branch
        self._thinking_chains[branch_chain_id] = branch_chain
        await self.db.mongo_insert_one("thinking_chains", branch_chain)
        
        self.logger.info(f"Created thinking branch {branch_chain_id} from {chain_id}")
        
        return branch_chain_id
    
    async def compare_chains(self, chain_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple thinking chains"""
        
        chains = []
        for chain_id in chain_ids:
            if chain_id in self._thinking_chains:
                chains.append(self._thinking_chains[chain_id])
        
        if len(chains) < 2:
            raise ValueError("Need at least 2 chains to compare")
        
        comparison = {
            "chains_compared": len(chains),
            "chain_analyses": [],
            "comparison_metrics": {},
            "recommendation": None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Analyze each chain
        for chain in chains:
            analysis = await self._analyze_thinking_chain(chain)
            comparison["chain_analyses"].append({
                "chain_id": chain["chain_id"],
                "analysis": analysis
            })
        
        # Compare metrics
        comparison["comparison_metrics"] = await self._compare_chain_metrics(chains)
        
        # Generate recommendation
        comparison["recommendation"] = await self._recommend_best_chain(chains)
        
        return comparison
    
    async def get_thinking_patterns(self, session_id: str) -> Dict[str, Any]:
        """Analyze thinking patterns for a session"""
        
        # Get all chains for session
        session_chains = [
            chain for chain in self._thinking_chains.values()
            if chain["session_id"] == session_id
        ]
        
        if not session_chains:
            return {"message": "No thinking chains found for session"}
        
        patterns = {
            "total_chains": len(session_chains),
            "reasoning_types": {},
            "step_patterns": {},
            "confidence_trends": [],
            "common_steps": [],
            "success_patterns": {}
        }
        
        # Analyze patterns
        for chain in session_chains:
            reasoning_type = chain["reasoning_type"]
            patterns["reasoning_types"][reasoning_type] = patterns["reasoning_types"].get(reasoning_type, 0) + 1
            
            for step in chain["steps"]:
                step_type = step["step_type"]
                patterns["step_patterns"][step_type] = patterns["step_patterns"].get(step_type, 0) + 1
                
                patterns["confidence_trends"].append({
                    "timestamp": step["timestamp"],
                    "confidence": step["confidence"],
                    "step_type": step_type
                })
        
        return patterns
    
    # Private helper methods
    async def _load_thinking_chains(self):
        """Load thinking chains from database"""
        try:
            chains = await self.db.mongo_find_many("thinking_chains", {"status": "active"})
            for chain in chains:
                self._thinking_chains[chain["chain_id"]] = chain
        except Exception as e:
            self.logger.error(f"Failed to load thinking chains: {e}")
    
    async def _save_thinking_chains(self):
        """Save thinking chains to database"""
        # Individual operations handle database updates
        pass
    
    async def _initialize_reasoning_patterns(self):
        """Initialize common reasoning patterns"""
        self._reasoning_patterns = {
            "deductive": {
                "steps": [ThinkingStep.PROBLEM_ANALYSIS, ThinkingStep.LOGICAL_REASONING, ThinkingStep.SOLUTION_SYNTHESIS],
                "description": "General principles to specific conclusions"
            },
            "inductive": {
                "steps": [ThinkingStep.EVIDENCE_GATHERING, ThinkingStep.HYPOTHESIS_FORMATION, ThinkingStep.VALIDATION],
                "description": "Specific observations to general principles"
            },
            "systematic": {
                "steps": [ThinkingStep.PROBLEM_ANALYSIS, ThinkingStep.EVIDENCE_GATHERING, 
                         ThinkingStep.LOGICAL_REASONING, ThinkingStep.SOLUTION_SYNTHESIS, ThinkingStep.VALIDATION],
                "description": "Comprehensive step-by-step approach"
            }
        }
    
    async def _analyze_thinking_chain(self, chain: Dict) -> Dict[str, Any]:
        """Analyze a thinking chain for quality metrics"""
        steps = chain["steps"]
        
        if not steps:
            return {"error": "No steps in chain"}
        
        # Calculate metrics
        total_steps = len(steps)
        validated_steps = sum(1 for step in steps if step.get("validated", False))
        average_confidence = sum(step["confidence"] for step in steps) / total_steps
        
        # Check logical consistency
        logical_consistency = await self._check_logical_consistency(steps)
        
        # Assess evidence strength
        evidence_strength = await self._assess_evidence_strength(steps)
        
        return {
            "total_steps": total_steps,
            "validated_steps": validated_steps,
            "validation_rate": validated_steps / total_steps if total_steps > 0 else 0,
            "average_confidence": average_confidence,
            "logical_consistency": logical_consistency,
            "evidence_strength": evidence_strength,
            "reasoning_type": chain["reasoning_type"]
        }
    
    async def _check_logical_consistency(self, steps: List[Dict]) -> float:
        """Check logical consistency of steps"""
        # Simple consistency check based on dependencies
        consistency_score = 1.0
        
        for step in steps:
            dependencies = step.get("dependencies", [])
            for dep_id in dependencies:
                # Check if dependency exists and is validated
                dep_exists = any(s["step_id"] == dep_id for s in steps)
                if not dep_exists:
                    consistency_score *= 0.8
        
        return consistency_score
    
    async def _assess_evidence_strength(self, steps: List[Dict]) -> float:
        """Assess the strength of evidence in the chain"""
        evidence_steps = [s for s in steps if s["step_type"] == ThinkingStep.EVIDENCE_GATHERING.value]
        
        if not evidence_steps:
            return 0.5  # Neutral if no evidence steps
        
        # Simple assessment based on evidence presence and validation
        total_evidence = len(evidence_steps)
        validated_evidence = sum(1 for step in evidence_steps if step.get("validated", False))
        
        return validated_evidence / total_evidence if total_evidence > 0 else 0.5
    
    async def _generate_solution_summary(self, chain: Dict) -> str:
        """Generate a summary of the solution"""
        steps = chain["steps"]
        solution_steps = [s for s in steps if s["step_type"] == ThinkingStep.SOLUTION_SYNTHESIS.value]
        
        if solution_steps:
            return solution_steps[-1]["content"]
        
        # Generate summary from all steps
        summary_parts = []
        for step in steps:
            if step["confidence"] > 0.7:  # High confidence steps
                summary_parts.append(step["content"][:100])
        
        return " | ".join(summary_parts)
    
    async def _compare_chain_metrics(self, chains: List[Dict]) -> Dict[str, Any]:
        """Compare metrics across chains"""
        metrics = {}
        
        for chain in chains:
            analysis = await self._analyze_thinking_chain(chain)
            chain_id = chain["chain_id"]
            metrics[chain_id] = analysis
        
        return metrics
    
    async def _recommend_best_chain(self, chains: List[Dict]) -> Dict[str, Any]:
        """Recommend the best chain based on analysis"""
        best_chain = None
        best_score = 0
        
        for chain in chains:
            analysis = await self._analyze_thinking_chain(chain)
            
            # Calculate composite score
            score = (
                analysis["average_confidence"] * 0.3 +
                analysis["logical_consistency"] * 0.3 +
                analysis["evidence_strength"] * 0.2 +
                analysis["validation_rate"] * 0.2
            )
            
            if score > best_score:
                best_score = score
                best_chain = chain
        
        return {
            "recommended_chain": best_chain["chain_id"] if best_chain else None,
            "score": best_score,
            "reasoning": "Based on confidence, consistency, evidence, and validation"
        }
