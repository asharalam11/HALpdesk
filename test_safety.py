#!/usr/bin/env python3
"""Test safety checker functionality"""
from halpdesk.daemon.safety import CommandSafetyChecker, SafetyLevel

def test_safety_checker():
    """Test command safety checking"""
    print("🛡️ Testing Command Safety Checker...")
    
    test_cases = [
        # Safe commands
        ("ls -la", SafetyLevel.SAFE),
        ("pwd", SafetyLevel.SAFE),
        ("echo hello", SafetyLevel.SAFE),
        ("cat file.txt", SafetyLevel.SAFE),
        
        # Warning commands  
        ("mv file1 file2", SafetyLevel.WARNING),
        ("cp file1 file2", SafetyLevel.WARNING),
        ("chmod 755 file", SafetyLevel.WARNING),
        ("sudo ls", SafetyLevel.WARNING),
        
        # Dangerous commands
        ("rm -rf /", SafetyLevel.DANGEROUS),
        ("rm -rf *", SafetyLevel.DANGEROUS),
        ("rm file", SafetyLevel.DANGEROUS),
        ("dd if=/dev/zero of=/dev/sda", SafetyLevel.DANGEROUS),
        ("sudo rm -rf /", SafetyLevel.DANGEROUS),
    ]
    
    passed = 0
    failed = 0
    
    for command, expected_level in test_cases:
        level, reason = CommandSafetyChecker.check_command(command)
        if level == expected_level:
            print(f"   ✅ '{command}' → {level} ({reason})")
            passed += 1
        else:
            print(f"   ❌ '{command}' → Expected {expected_level}, got {level}")
            failed += 1
    
    print(f"\n📊 Safety tests: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All safety tests passed!")
    else:
        print("⚠️ Some safety tests failed")

if __name__ == "__main__":
    test_safety_checker()