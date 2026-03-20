"""
Smart Contract Parser and Engine (HSU-Spec Section 3.9)
========================================================

Implements the BNF grammar for smart contracts:

<contract>      ::= "contract" <id> "{" <rule>* "}"
<rule>          ::= <permission> | <limit> | <delegation>
<permission>    ::= "allow" <agent> "to" <action>
<limit>         ::= "limit" <action> "to" <integer>
<delegation>    ::= "delegate" <action> "to" <agent>
<agent>         ::= "agent:" <hash>
<action>        ::= "read" | "write" | "execute"
<integer>       ::= [0-9]+

A contract is itself a Layer-3 node.
"""

import hashlib
import json
import re
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ============== TOKEN TYPES ==============

class TokenType(Enum):
    CONTRACT = "CONTRACT"
    ALLOW = "ALLOW"
    LIMIT = "LIMIT"
    DELEGATE = "DELEGATE"
    TO = "TO"
    AGENT = "AGENT"
    ACTION = "ACTION"
    INTEGER = "INTEGER"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    COLON = "COLON"
    IDENTIFIER = "IDENTIFIER"
    HASH = "HASH"
    EOF = "EOF"
    NEWLINE = "NEWLINE"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int


# ============== ACTION TYPES ==============

class ActionType(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    
    @classmethod
    def from_string(cls, s: str) -> "ActionType":
        return cls(s.lower())


# ============== RULE TYPES ==============

class RuleType(Enum):
    PERMISSION = "permission"
    LIMIT = "limit"
    DELEGATION = "delegation"


@dataclass
class Permission:
    """allow <agent> to <action>"""
    agent_hash: str
    action: ActionType
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": RuleType.PERMISSION.value,
            "agent": self.agent_hash,
            "action": self.action.value,
        }


@dataclass
class Limit:
    """limit <action> to <integer>"""
    action: ActionType
    max_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": RuleType.LIMIT.value,
            "action": self.action.value,
            "max_count": self.max_count,
        }


@dataclass
class Delegation:
    """delegate <action> to <agent>"""
    action: ActionType
    agent_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": RuleType.DELEGATION.value,
            "action": self.action.value,
            "agent": self.agent_hash,
        }


Rule = Union[Permission, Limit, Delegation]


@dataclass
class Contract:
    """A parsed smart contract"""
    contract_id: str
    name: str
    rules: List[Rule] = field(default_factory=list)
    signatures: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "name": self.name,
            "rules": [r.to_dict() for r in self.rules],
            "signatures": self.signatures,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
        }
    
    def compute_hash(self) -> str:
        """Compute contract hash for Layer-3 node"""
        content = json.dumps({
            "name": self.name,
            "rules": [r.to_dict() for r in self.rules],
            "version": self.version,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


# ============== LEXER ==============

class ContractLexer:
    """Tokenizer for smart contract DSL"""
    
    KEYWORDS = {
        "contract": TokenType.CONTRACT,
        "allow": TokenType.ALLOW,
        "limit": TokenType.LIMIT,
        "delegate": TokenType.DELEGATE,
        "to": TokenType.TO,
        "agent": TokenType.AGENT,
        "read": TokenType.ACTION,
        "write": TokenType.ACTION,
        "execute": TokenType.ACTION,
    }
    
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
    
    def _current_char(self) -> Optional[str]:
        if self.pos >= len(self.source):
            return None
        return self.source[self.pos]
    
    def _peek(self, offset: int = 1) -> Optional[str]:
        pos = self.pos + offset
        if pos >= len(self.source):
            return None
        return self.source[pos]
    
    def _advance(self) -> str:
        char = self._current_char()
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char
    
    def _skip_whitespace(self):
        while self._current_char() and self._current_char() in ' \t\r':
            self._advance()
    
    def _skip_comment(self):
        if self._current_char() == '#':
            while self._current_char() and self._current_char() != '\n':
                self._advance()
    
    def _read_identifier(self) -> str:
        result = ""
        while self._current_char() and (self._current_char().isalnum() or self._current_char() == '_'):
            result += self._advance()
        return result
    
    def _read_hash(self) -> str:
        """Read a hex hash or alphanumeric identifier"""
        result = ""
        while self._current_char() and (self._current_char().isalnum() or self._current_char() == '_'):
            result += self._advance()
        return result.lower()
    
    def _read_integer(self) -> str:
        result = ""
        while self._current_char() and self._current_char().isdigit():
            result += self._advance()
        return result
    
    def tokenize(self) -> List[Token]:
        """Tokenize the source code"""
        self.tokens = []
        
        while self._current_char():
            self._skip_whitespace()
            self._skip_comment()
            
            if not self._current_char():
                break
            
            char = self._current_char()
            line, col = self.line, self.column
            
            if char == '\n':
                self._advance()
                self.tokens.append(Token(TokenType.NEWLINE, "\\n", line, col))
            elif char == '{':
                self._advance()
                self.tokens.append(Token(TokenType.LBRACE, "{", line, col))
            elif char == '}':
                self._advance()
                self.tokens.append(Token(TokenType.RBRACE, "}", line, col))
            elif char == ':':
                self._advance()
                self.tokens.append(Token(TokenType.COLON, ":", line, col))
            elif char.isalpha() or char == '_':
                ident = self._read_identifier()
                token_type = self.KEYWORDS.get(ident.lower(), TokenType.IDENTIFIER)
                self.tokens.append(Token(token_type, ident, line, col))
            elif char.isdigit():
                num = self._read_integer()
                self.tokens.append(Token(TokenType.INTEGER, num, line, col))
            elif char in '0123456789abcdefABCDEF':
                hash_val = self._read_hash()
                self.tokens.append(Token(TokenType.HASH, hash_val, line, col))
            else:
                self._advance()  # Skip unknown characters
        
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens


# ============== PARSER ==============

class ParseError(Exception):
    """Contract parsing error"""
    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"Parse error at line {line}, column {column}: {message}")


class ContractParser:
    """
    Parser for smart contract DSL
    
    Grammar:
    <contract>      ::= "contract" <id> "{" <rule>* "}"
    <rule>          ::= <permission> | <limit> | <delegation>
    <permission>    ::= "allow" <agent> "to" <action>
    <limit>         ::= "limit" <action> "to" <integer>
    <delegation>    ::= "delegate" <action> "to" <agent>
    <agent>         ::= "agent:" <hash>
    <action>        ::= "read" | "write" | "execute"
    """
    
    def __init__(self, tokens: List[Token]):
        self.tokens = [t for t in tokens if t.type != TokenType.NEWLINE]
        self.pos = 0
    
    def _current(self) -> Token:
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]
    
    def _peek(self, offset: int = 1) -> Token:
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[pos]
    
    def _advance(self) -> Token:
        token = self._current()
        self.pos += 1
        return token
    
    def _expect(self, token_type: TokenType) -> Token:
        token = self._current()
        if token.type != token_type:
            raise ParseError(
                f"Expected {token_type.value}, got {token.type.value}",
                token.line,
                token.column
            )
        return self._advance()
    
    def _match(self, *token_types: TokenType) -> bool:
        return self._current().type in token_types
    
    def parse(self) -> Contract:
        """Parse a contract definition"""
        return self._parse_contract()
    
    def _parse_contract(self) -> Contract:
        """<contract> ::= "contract" <id> "{" <rule>* "}" """
        self._expect(TokenType.CONTRACT)
        
        name_token = self._expect(TokenType.IDENTIFIER)
        name = name_token.value
        
        self._expect(TokenType.LBRACE)
        
        rules = []
        while not self._match(TokenType.RBRACE, TokenType.EOF):
            rule = self._parse_rule()
            if rule:
                rules.append(rule)
        
        self._expect(TokenType.RBRACE)
        
        contract = Contract(
            contract_id="",  # Will be computed
            name=name,
            rules=rules,
        )
        contract.contract_id = contract.compute_hash()
        
        return contract
    
    def _parse_rule(self) -> Optional[Rule]:
        """<rule> ::= <permission> | <limit> | <delegation>"""
        if self._match(TokenType.ALLOW):
            return self._parse_permission()
        elif self._match(TokenType.LIMIT):
            return self._parse_limit()
        elif self._match(TokenType.DELEGATE):
            return self._parse_delegation()
        else:
            # Skip unknown tokens
            self._advance()
            return None
    
    def _parse_permission(self) -> Permission:
        """<permission> ::= "allow" <agent> "to" <action>"""
        self._expect(TokenType.ALLOW)
        agent_hash = self._parse_agent()
        self._expect(TokenType.TO)
        action = self._parse_action()
        
        return Permission(agent_hash=agent_hash, action=action)
    
    def _parse_limit(self) -> Limit:
        """<limit> ::= "limit" <action> "to" <integer>"""
        self._expect(TokenType.LIMIT)
        action = self._parse_action()
        self._expect(TokenType.TO)
        count_token = self._expect(TokenType.INTEGER)
        
        return Limit(action=action, max_count=int(count_token.value))
    
    def _parse_delegation(self) -> Delegation:
        """<delegation> ::= "delegate" <action> "to" <agent>"""
        self._expect(TokenType.DELEGATE)
        action = self._parse_action()
        self._expect(TokenType.TO)
        agent_hash = self._parse_agent()
        
        return Delegation(action=action, agent_hash=agent_hash)
    
    def _parse_agent(self) -> str:
        """<agent> ::= "agent:" <hash>"""
        self._expect(TokenType.AGENT)
        self._expect(TokenType.COLON)
        
        # Accept either HASH or IDENTIFIER (for short hashes)
        if self._match(TokenType.HASH):
            return self._advance().value
        elif self._match(TokenType.IDENTIFIER):
            return self._advance().value
        else:
            token = self._current()
            raise ParseError(
                f"Expected hash, got {token.type.value}",
                token.line,
                token.column
            )
    
    def _parse_action(self) -> ActionType:
        """<action> ::= "read" | "write" | "execute" """
        token = self._expect(TokenType.ACTION)
        return ActionType.from_string(token.value)


# ============== CONTRACT ENGINE ==============

@dataclass
class ContractExecution:
    """Result of contract rule evaluation"""
    allowed: bool
    rule_matched: Optional[Rule] = None
    reason: str = ""


class ContractEngine:
    """
    Smart Contract Execution Engine
    
    Evaluates contracts against actions and enforces rules.
    """
    
    def __init__(self):
        self._contracts: Dict[str, Contract] = {}
        self._action_counts: Dict[str, Dict[str, int]] = {}  # contract_id -> action -> count
    
    def register_contract(self, contract: Contract):
        """Register a contract for enforcement"""
        self._contracts[contract.contract_id] = contract
        self._action_counts[contract.contract_id] = {
            "read": 0,
            "write": 0,
            "execute": 0,
        }
        logger.info(f"📜 Registered contract: {contract.name} ({contract.contract_id[:16]}...)")
    
    def get_contract(self, contract_id: str) -> Optional[Contract]:
        """Get a registered contract"""
        return self._contracts.get(contract_id)
    
    def evaluate(
        self,
        contract_id: str,
        agent_hash: str,
        action: ActionType,
    ) -> ContractExecution:
        """
        Evaluate if an action is allowed by a contract.
        
        Checks:
        1. Permission rules (allow agent to action)
        2. Limit rules (limit action to N)
        3. Delegation rules (delegate action to agent)
        """
        contract = self._contracts.get(contract_id)
        if not contract:
            return ContractExecution(
                allowed=False,
                reason=f"Contract not found: {contract_id}"
            )
        
        # Check limits first
        for rule in contract.rules:
            if isinstance(rule, Limit) and rule.action == action:
                current_count = self._action_counts[contract_id].get(action.value, 0)
                if current_count >= rule.max_count:
                    return ContractExecution(
                        allowed=False,
                        rule_matched=rule,
                        reason=f"Limit exceeded: {action.value} limited to {rule.max_count}"
                    )
        
        # Check permissions
        for rule in contract.rules:
            if isinstance(rule, Permission):
                if rule.agent_hash == agent_hash and rule.action == action:
                    # Increment action count
                    self._action_counts[contract_id][action.value] += 1
                    return ContractExecution(
                        allowed=True,
                        rule_matched=rule,
                        reason=f"Permission granted: {agent_hash[:16]}... can {action.value}"
                    )
        
        # Check delegations
        for rule in contract.rules:
            if isinstance(rule, Delegation):
                if rule.agent_hash == agent_hash and rule.action == action:
                    self._action_counts[contract_id][action.value] += 1
                    return ContractExecution(
                        allowed=True,
                        rule_matched=rule,
                        reason=f"Delegation granted: {action.value} delegated to {agent_hash[:16]}..."
                    )
        
        return ContractExecution(
            allowed=False,
            reason=f"No matching rule for agent {agent_hash[:16]}... to {action.value}"
        )
    
    def reset_counts(self, contract_id: str):
        """Reset action counts for a contract"""
        if contract_id in self._action_counts:
            self._action_counts[contract_id] = {
                "read": 0,
                "write": 0,
                "execute": 0,
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return {
            "registered_contracts": len(self._contracts),
            "action_counts": self._action_counts,
        }


# ============== CONVENIENCE FUNCTIONS ==============

def parse_contract(source: str) -> Contract:
    """Parse a contract from source code"""
    lexer = ContractLexer(source)
    tokens = lexer.tokenize()
    parser = ContractParser(tokens)
    return parser.parse()


def validate_contract(source: str) -> Tuple[bool, Optional[str]]:
    """Validate contract syntax without executing"""
    try:
        parse_contract(source)
        return True, None
    except ParseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


# Global engine instance
contract_engine = ContractEngine()


# ============== EXAMPLE USAGE ==============

EXAMPLE_CONTRACT = """
contract AgentAccessControl {
    # Allow specific agent to read
    allow agent:abc123def456 to read
    
    # Allow another agent to write
    allow agent:789xyz000111 to write
    
    # Limit executions to 100 per period
    limit execute to 100
    
    # Delegate execute to a trusted agent
    delegate execute to agent:trustedagent123
}
"""

if __name__ == "__main__":
    # Test the parser
    contract = parse_contract(EXAMPLE_CONTRACT)
    print(f"Contract: {contract.name}")
    print(f"ID: {contract.contract_id}")
    print(f"Rules: {len(contract.rules)}")
    for rule in contract.rules:
        print(f"  - {rule.to_dict()}")
