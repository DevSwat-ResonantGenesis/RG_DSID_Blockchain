"""
DSID-P Section 68.4: Formal Governance DSL Implementation
==========================================================

A domain-specific language (DSL) for defining governance rules
that can be parsed, validated, and executed deterministically.

DSL Syntax Example:
    rule AllowInvoicePayment {
        when agent.role == "finance"
        and semantic.domain == "payments"
        and amount < 50000
        allow
    }

This provides:
- Rule portability across systems
- Deterministic evaluation
- Version-controlled governance
- Human-readable rules
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


# ============== DSL TOKEN TYPES ==============

class TokenType(Enum):
    """Token types for the governance DSL."""
    RULE = "rule"
    WHEN = "when"
    AND = "and"
    OR = "or"
    NOT = "not"
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"
    IDENTIFIER = "identifier"
    OPERATOR = "operator"
    VALUE = "value"
    LBRACE = "lbrace"
    RBRACE = "rbrace"
    LPAREN = "lparen"
    RPAREN = "rparen"
    DOT = "dot"
    COMMA = "comma"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    EOF = "eof"


@dataclass
class Token:
    """A token from the DSL lexer."""
    type: TokenType
    value: Any
    line: int = 0
    column: int = 0


# ============== DSL LEXER ==============

class GovernanceLexer:
    """
    Lexer for the Governance DSL.
    
    Tokenizes governance rule definitions.
    """
    
    KEYWORDS = {
        "rule": TokenType.RULE,
        "when": TokenType.WHEN,
        "and": TokenType.AND,
        "or": TokenType.OR,
        "not": TokenType.NOT,
        "allow": TokenType.ALLOW,
        "deny": TokenType.DENY,
        "escalate": TokenType.ESCALATE,
        "true": TokenType.BOOLEAN,
        "false": TokenType.BOOLEAN,
    }
    
    OPERATORS = ["==", "!=", "<=", ">=", "<", ">", "in", "contains", "matches"]
    
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
    
    def tokenize(self) -> List[Token]:
        """Tokenize the source code."""
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break
            
            char = self.source[self.pos]
            
            # Single character tokens
            if char == "{":
                self.tokens.append(Token(TokenType.LBRACE, "{", self.line, self.column))
                self._advance()
            elif char == "}":
                self.tokens.append(Token(TokenType.RBRACE, "}", self.line, self.column))
                self._advance()
            elif char == "(":
                self.tokens.append(Token(TokenType.LPAREN, "(", self.line, self.column))
                self._advance()
            elif char == ")":
                self.tokens.append(Token(TokenType.RPAREN, ")", self.line, self.column))
                self._advance()
            elif char == ".":
                self.tokens.append(Token(TokenType.DOT, ".", self.line, self.column))
                self._advance()
            elif char == ",":
                self.tokens.append(Token(TokenType.COMMA, ",", self.line, self.column))
                self._advance()
            elif char == '"' or char == "'":
                self._read_string(char)
            elif char.isdigit() or (char == "-" and self._peek().isdigit()):
                self._read_number()
            elif char.isalpha() or char == "_":
                self._read_identifier()
            elif self._is_operator_start():
                self._read_operator()
            elif char == "#":
                self._skip_comment()
            else:
                self._advance()
        
        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens
    
    def _advance(self):
        """Advance to next character."""
        if self.source[self.pos] == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.pos += 1
    
    def _peek(self) -> str:
        """Peek at next character."""
        if self.pos + 1 < len(self.source):
            return self.source[self.pos + 1]
        return ""
    
    def _skip_whitespace(self):
        """Skip whitespace characters."""
        while self.pos < len(self.source) and self.source[self.pos].isspace():
            self._advance()
    
    def _skip_comment(self):
        """Skip comment until end of line."""
        while self.pos < len(self.source) and self.source[self.pos] != "\n":
            self._advance()
    
    def _read_string(self, quote: str):
        """Read a string literal."""
        start_line, start_col = self.line, self.column
        self._advance()  # Skip opening quote
        value = ""
        while self.pos < len(self.source) and self.source[self.pos] != quote:
            if self.source[self.pos] == "\\":
                self._advance()
                if self.pos < len(self.source):
                    value += self.source[self.pos]
                    self._advance()
            else:
                value += self.source[self.pos]
                self._advance()
        self._advance()  # Skip closing quote
        self.tokens.append(Token(TokenType.STRING, value, start_line, start_col))
    
    def _read_number(self):
        """Read a numeric literal."""
        start_line, start_col = self.line, self.column
        value = ""
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] in ".-"):
            value += self.source[self.pos]
            self._advance()
        
        if "." in value:
            self.tokens.append(Token(TokenType.NUMBER, float(value), start_line, start_col))
        else:
            self.tokens.append(Token(TokenType.NUMBER, int(value), start_line, start_col))
    
    def _read_identifier(self):
        """Read an identifier or keyword."""
        start_line, start_col = self.line, self.column
        value = ""
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            value += self.source[self.pos]
            self._advance()
        
        lower_value = value.lower()
        if lower_value in self.KEYWORDS:
            token_type = self.KEYWORDS[lower_value]
            if token_type == TokenType.BOOLEAN:
                self.tokens.append(Token(token_type, lower_value == "true", start_line, start_col))
            else:
                self.tokens.append(Token(token_type, value, start_line, start_col))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, value, start_line, start_col))
    
    def _is_operator_start(self) -> bool:
        """Check if current position starts an operator."""
        for op in self.OPERATORS:
            if self.source[self.pos:self.pos + len(op)] == op:
                return True
        return False
    
    def _read_operator(self):
        """Read an operator."""
        start_line, start_col = self.line, self.column
        for op in sorted(self.OPERATORS, key=len, reverse=True):
            if self.source[self.pos:self.pos + len(op)] == op:
                self.tokens.append(Token(TokenType.OPERATOR, op, start_line, start_col))
                for _ in range(len(op)):
                    self._advance()
                return


# ============== DSL AST NODES ==============

@dataclass
class ASTNode:
    """Base AST node."""
    pass


@dataclass
class RuleNode(ASTNode):
    """A governance rule."""
    name: str
    conditions: List['ConditionNode']
    action: str  # "allow", "deny", "escalate"
    escalation_target: Optional[str] = None


@dataclass
class ConditionNode(ASTNode):
    """A condition expression."""
    left: str  # e.g., "agent.role"
    operator: str  # e.g., "=="
    right: Any  # e.g., "finance"
    connector: Optional[str] = None  # "and" or "or"


@dataclass
class RuleSetNode(ASTNode):
    """A set of governance rules."""
    rules: List[RuleNode]
    version: str = "1.0"


# ============== DSL PARSER ==============

class GovernanceParser:
    """
    Parser for the Governance DSL.
    
    Parses tokens into an AST.
    """
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
    
    def parse(self) -> RuleSetNode:
        """Parse all rules into a RuleSet."""
        rules = []
        while not self._is_at_end():
            if self._check(TokenType.RULE):
                rules.append(self._parse_rule())
            else:
                self._advance()
        return RuleSetNode(rules=rules)
    
    def _parse_rule(self) -> RuleNode:
        """Parse a single rule."""
        self._consume(TokenType.RULE, "Expected 'rule'")
        name = self._consume(TokenType.IDENTIFIER, "Expected rule name").value
        self._consume(TokenType.LBRACE, "Expected '{'")
        
        # Parse conditions
        conditions = []
        if self._check(TokenType.WHEN):
            self._advance()
            conditions = self._parse_conditions()
        
        # Parse action
        action = "deny"
        escalation_target = None
        
        if self._check(TokenType.ALLOW):
            self._advance()
            action = "allow"
        elif self._check(TokenType.DENY):
            self._advance()
            action = "deny"
        elif self._check(TokenType.ESCALATE):
            self._advance()
            action = "escalate"
            if self._check(TokenType.STRING):
                escalation_target = self._advance().value
        
        self._consume(TokenType.RBRACE, "Expected '}'")
        
        return RuleNode(
            name=name,
            conditions=conditions,
            action=action,
            escalation_target=escalation_target
        )
    
    def _parse_conditions(self) -> List[ConditionNode]:
        """Parse condition expressions."""
        conditions = []
        
        # Parse first condition
        cond = self._parse_condition()
        if cond:
            conditions.append(cond)
        
        # Parse additional conditions with connectors
        while self._check(TokenType.AND) or self._check(TokenType.OR):
            connector = "and" if self._check(TokenType.AND) else "or"
            self._advance()
            cond = self._parse_condition()
            if cond:
                cond.connector = connector
                conditions.append(cond)
        
        return conditions
    
    def _parse_condition(self) -> Optional[ConditionNode]:
        """Parse a single condition."""
        if not self._check(TokenType.IDENTIFIER):
            return None
        
        # Parse left side (e.g., agent.role)
        left_parts = [self._advance().value]
        while self._check(TokenType.DOT):
            self._advance()
            if self._check(TokenType.IDENTIFIER):
                left_parts.append(self._advance().value)
        left = ".".join(left_parts)
        
        # Parse operator
        if not self._check(TokenType.OPERATOR):
            return None
        operator = self._advance().value
        
        # Parse right side
        right = None
        if self._check(TokenType.STRING):
            right = self._advance().value
        elif self._check(TokenType.NUMBER):
            right = self._advance().value
        elif self._check(TokenType.BOOLEAN):
            right = self._advance().value
        elif self._check(TokenType.IDENTIFIER):
            right = self._advance().value
        
        return ConditionNode(left=left, operator=operator, right=right)
    
    def _check(self, token_type: TokenType) -> bool:
        """Check if current token is of given type."""
        if self._is_at_end():
            return False
        return self.tokens[self.pos].type == token_type
    
    def _advance(self) -> Token:
        """Advance and return current token."""
        if not self._is_at_end():
            self.pos += 1
        return self.tokens[self.pos - 1]
    
    def _consume(self, token_type: TokenType, message: str) -> Token:
        """Consume expected token or raise error."""
        if self._check(token_type):
            return self._advance()
        raise SyntaxError(f"{message} at line {self.tokens[self.pos].line}")
    
    def _is_at_end(self) -> bool:
        """Check if at end of tokens."""
        return self.tokens[self.pos].type == TokenType.EOF


# ============== DSL EVALUATOR ==============

class GovernanceEvaluator:
    """
    Evaluator for the Governance DSL.
    
    Evaluates rules against a context.
    """
    
    def __init__(self, rule_set: RuleSetNode):
        self.rule_set = rule_set
    
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate all rules against context.
        
        Returns first matching rule result.
        """
        for rule in self.rule_set.rules:
            if self._evaluate_rule(rule, context):
                return {
                    "rule": rule.name,
                    "action": rule.action,
                    "allowed": rule.action == "allow",
                    "escalate": rule.action == "escalate",
                    "escalation_target": rule.escalation_target,
                }
        
        # Default: deny
        return {
            "rule": None,
            "action": "deny",
            "allowed": False,
            "escalate": False,
            "reason": "No matching rule"
        }
    
    def _evaluate_rule(self, rule: RuleNode, context: Dict[str, Any]) -> bool:
        """Evaluate a single rule."""
        if not rule.conditions:
            return True
        
        result = True
        for i, cond in enumerate(rule.conditions):
            cond_result = self._evaluate_condition(cond, context)
            
            if i == 0:
                result = cond_result
            elif cond.connector == "and":
                result = result and cond_result
            elif cond.connector == "or":
                result = result or cond_result
        
        return result
    
    def _evaluate_condition(self, cond: ConditionNode, context: Dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        # Get left value from context
        left_value = self._get_context_value(cond.left, context)
        right_value = cond.right
        
        # Evaluate operator
        if cond.operator == "==":
            return left_value == right_value
        elif cond.operator == "!=":
            return left_value != right_value
        elif cond.operator == "<":
            return left_value < right_value
        elif cond.operator == "<=":
            return left_value <= right_value
        elif cond.operator == ">":
            return left_value > right_value
        elif cond.operator == ">=":
            return left_value >= right_value
        elif cond.operator == "in":
            return left_value in right_value
        elif cond.operator == "contains":
            return right_value in left_value
        elif cond.operator == "matches":
            return bool(re.match(right_value, str(left_value)))
        
        return False
    
    def _get_context_value(self, path: str, context: Dict[str, Any]) -> Any:
        """Get a value from context using dot notation."""
        parts = path.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value


# ============== DSL COMPILER ==============

class GovernanceDSL:
    """
    Main interface for the Governance DSL.
    
    Provides compile(), load(), and evaluate() methods.
    """
    
    def __init__(self):
        self.rule_set: Optional[RuleSetNode] = None
        self.evaluator: Optional[GovernanceEvaluator] = None
    
    def compile(self, source: str) -> RuleSetNode:
        """
        Compile DSL source into a RuleSet.
        
        Args:
            source: DSL source code
            
        Returns:
            Compiled RuleSetNode
        """
        lexer = GovernanceLexer(source)
        tokens = lexer.tokenize()
        parser = GovernanceParser(tokens)
        self.rule_set = parser.parse()
        self.evaluator = GovernanceEvaluator(self.rule_set)
        return self.rule_set
    
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate rules against context.
        
        Args:
            context: Evaluation context with agent/semantic/action data
            
        Returns:
            Evaluation result
        """
        if not self.evaluator:
            raise RuntimeError("No rules compiled. Call compile() first.")
        return self.evaluator.evaluate(context)
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all compiled rules as dictionaries."""
        if not self.rule_set:
            return []
        return [
            {
                "name": r.name,
                "conditions": [
                    {"left": c.left, "operator": c.operator, "right": c.right, "connector": c.connector}
                    for c in r.conditions
                ],
                "action": r.action,
                "escalation_target": r.escalation_target
            }
            for r in self.rule_set.rules
        ]
    
    def to_json(self) -> str:
        """Export rules as JSON."""
        import json
        return json.dumps(self.get_rules(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'GovernanceDSL':
        """Import rules from JSON."""
        import json
        data = json.loads(json_str)
        
        # Reconstruct DSL source
        source_lines = []
        for rule_data in data:
            source_lines.append(f"rule {rule_data['name']} {{")
            if rule_data.get("conditions"):
                cond_strs = []
                for c in rule_data["conditions"]:
                    right = f'"{c["right"]}"' if isinstance(c["right"], str) else c["right"]
                    cond_str = f'{c["left"]} {c["operator"]} {right}'
                    if c.get("connector"):
                        cond_str = f'{c["connector"]} {cond_str}'
                    cond_strs.append(cond_str)
                source_lines.append(f"    when {' '.join(cond_strs)}")
            source_lines.append(f"    {rule_data['action']}")
            source_lines.append("}")
            source_lines.append("")
        
        dsl = cls()
        dsl.compile("\n".join(source_lines))
        return dsl


# ============== EXAMPLE RULES ==============

EXAMPLE_RULES = '''
# DSID-P Default Governance Rules

rule AllowFinancePayment {
    when agent.role == "finance"
    and semantic.domain == "payments"
    and amount < 50000
    allow
}

rule AllowReadOnly {
    when action.type == "read"
    allow
}

rule EscalateLargeTransaction {
    when amount >= 50000
    escalate "supervisor"
}

rule DenyExternalAccess {
    when agent.trust_score < 0.5
    and action.type == "external"
    deny
}

rule AllowHighTrust {
    when agent.trust_score >= 0.9
    allow
}

rule DefaultDeny {
    deny
}
'''


# Global DSL instance with default rules
governance_dsl = GovernanceDSL()
governance_dsl.compile(EXAMPLE_RULES)
