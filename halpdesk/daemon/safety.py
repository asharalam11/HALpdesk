"""Command safety checker for HALpdesk"""
import re
from typing import Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_provider import AIProvider

class SafetyLevel:
    SAFE = "🟢"
    WARNING = "🟡"
    DANGEROUS = "🔴"

class CommandSafetyChecker:
    def __init__(self, ai_provider: Optional['AIProvider'] = None):
        self.ai_provider = ai_provider

    # Fallback patterns for when AI is unavailable
    DANGEROUS_COMMANDS = {
        'rm': SafetyLevel.DANGEROUS,
        'rmdir': SafetyLevel.DANGEROUS,
        'dd': SafetyLevel.DANGEROUS,
        'mkfs': SafetyLevel.DANGEROUS,
        'fdisk': SafetyLevel.DANGEROUS,
        'format': SafetyLevel.DANGEROUS,
    }

    WARNING_COMMANDS = {
        'mv': SafetyLevel.WARNING,
        'cp': SafetyLevel.WARNING,
        'chmod': SafetyLevel.WARNING,
        'chown': SafetyLevel.WARNING,
        'sudo': SafetyLevel.WARNING,
        'su': SafetyLevel.WARNING,
        'wget': SafetyLevel.WARNING,
        'curl': SafetyLevel.WARNING,
        'git reset --hard': SafetyLevel.WARNING,
    }

    DANGEROUS_PATTERNS = [
        r'rm\s+-rf\s*/',  # rm -rf /
        r'rm\s+-rf\s*\*',  # rm -rf *
        r':\(\)\{\s*:\|:\&\s*\}',  # Fork bomb
        r'dd\s+.*of=/dev/',  # Writing to devices
        r'>\s*/dev/sd[a-z]',  # Writing to disk devices
    ]
    
    def check_command(self, command: str) -> Tuple[str, str]:
        """Check command safety using AI evaluation and return (safety_level, reason)"""
        if self.ai_provider:
            return self._ai_safety_check(command)
        else:
            return self._fallback_safety_check(command)

    def _ai_safety_check(self, command: str) -> Tuple[str, str]:
        """Use AI to evaluate command safety"""
        try:
            safety_prompt = f"""Evaluate this bash command for safety and respond with ONLY one of these exact formats:

SAFE: [brief reason - command is read-only or benign]
WARNING: [brief reason - command modifies files/system but is recoverable]
DANGEROUS: [brief reason - command could cause data loss or system damage]

Command to evaluate: {command}

Response:"""

            response = self.ai_provider.chat(safety_prompt, {}).strip().upper()

            if response.startswith("DANGEROUS:"):
                reason = response[10:].strip()
                return SafetyLevel.DANGEROUS, reason or "AI detected high risk"
            elif response.startswith("WARNING:"):
                reason = response[8:].strip()
                return SafetyLevel.WARNING, reason or "AI detected moderate risk"
            elif response.startswith("SAFE:"):
                reason = response[5:].strip()
                return SafetyLevel.SAFE, reason or "AI confirmed safe"
            else:
                # Fallback if AI response format is unexpected
                return self._fallback_safety_check(command)

        except Exception:
            # Fallback to pattern matching if AI fails
            return self._fallback_safety_check(command)

    def _fallback_safety_check(self, command: str) -> Tuple[str, str]:
        """Fallback pattern-based safety check when AI is unavailable"""
        command = command.strip().lower()

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return SafetyLevel.DANGEROUS, "Potentially destructive pattern detected"

        # Extract first command word
        first_word = command.split()[0] if command.split() else ""

        # Check exact matches first
        if first_word in self.DANGEROUS_COMMANDS:
            return self.DANGEROUS_COMMANDS[first_word], f"'{first_word}' can be destructive"

        if first_word in self.WARNING_COMMANDS:
            return self.WARNING_COMMANDS[first_word], f"'{first_word}' modifies system state"

        # Check for sudo with dangerous commands
        if command.startswith('sudo '):
            remaining = command[5:].strip()
            remaining_first = remaining.split()[0] if remaining.split() else ""
            if remaining_first in self.DANGEROUS_COMMANDS:
                return SafetyLevel.DANGEROUS, f"sudo {remaining_first} can be very destructive"

        # Default to safe
        return SafetyLevel.SAFE, "Command appears safe"