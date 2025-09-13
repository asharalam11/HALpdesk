"""Command safety checker for HALpdesk"""
import re
from typing import Tuple

class SafetyLevel:
    SAFE = "🟢"
    WARNING = "🟡"  
    DANGEROUS = "🔴"

class CommandSafetyChecker:
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
    
    @classmethod
    def check_command(cls, command: str) -> Tuple[str, str]:
        """Check command safety and return (safety_level, reason)"""
        command = command.strip().lower()
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return SafetyLevel.DANGEROUS, "Potentially destructive pattern detected"
        
        # Extract first command word
        first_word = command.split()[0] if command.split() else ""
        
        # Check exact matches first
        if first_word in cls.DANGEROUS_COMMANDS:
            return cls.DANGEROUS_COMMANDS[first_word], f"'{first_word}' can be destructive"
        
        if first_word in cls.WARNING_COMMANDS:
            return cls.WARNING_COMMANDS[first_word], f"'{first_word}' modifies system state"
        
        # Check for sudo with dangerous commands
        if command.startswith('sudo '):
            remaining = command[5:].strip()
            remaining_first = remaining.split()[0] if remaining.split() else ""
            if remaining_first in cls.DANGEROUS_COMMANDS:
                return SafetyLevel.DANGEROUS, f"sudo {remaining_first} can be very destructive"
        
        # Default to safe
        return SafetyLevel.SAFE, "Command appears safe"