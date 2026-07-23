"""
Test Script: Compare BRD Generation Quality
Improved Agent v2 vs ChatGPT vs Copilot
"""

import json
from agents.brd_agent_v2 import generate_brd_improved

# === STEP 1: Extract content from your 2 source documents ===

PROJECT_DESC = """
Receipting Automation Using Receipt API - ABHFL Project

Currently, ABHFL Operations team uses RPA to:
1. Generate DRE files
2. Upload receipts into A3S LMS

Problem with RPA:
- Dependent on RPA bot maintenance
- Manual retry process
- Slow processing
- Limited visibility/reporting
- High operational risk

Solution:
Replace RPA with an automated front-end module that:
1. Operations users login via ADID
2. Upload receipt Excel file
3. System validates file
4. System prepares Receipt API request
5. Calls Receipt API directly
6. Stores response
7. Auto retries failed records every 3 hours
8. Users can manually retry failed records
9. Success & Failure dashboard
"""

CURRENT_PROCESS = """
Current RPA-Based Process:
1. Operations Team → Generate Receipt File
2. RPA Bot → Reads File
3. RPA Bot → Create DRE File
4. RPA Bot → Upload into A3S LMS
5. Manual Monitoring required
6. Manual retries on failures

Problems:
- Dependent on RPA
- Difficult maintenance
- Manual retries
- Slow processing
- Limited visibility
"""

BUSINESS_CONTEXT = """
Business Objectives:
1. Eliminate dependency on RPA
2. Automate receipt posting in A3S LMS
3. Improve processing efficiency and tracking
4. Enable automatic and manual retry mechanisms
5. Provide real-time reporting for success/failed transactions
6. Ensure secure access through ADID authentication

Expected Benefits:
- Eliminate dependency on RPA
- Faster receipt processing
- Reduced manual intervention
- Improved accuracy through API integration
- Automatic retry mechanism
- Better monitoring and reporting
- Complete audit trail
- Improved operational efficiency
"""

API_SPECS = """
Receipt API Integration

API Endpoint:
- UAT: https://ezgatewayuat.insideabc.com/omnifin-lms-api/loanReceiptAPI
- Production: https://ezgateway.insideabc.com/omnifin-lms-api/loanReceiptAPI

Request Payload Structure:
{
  "userCredentials": {
    "userId": "user1",
    "secureKey": "2a67870e-b55e-997a-fbff-9608fd31a844"
  },
  "loanNo": "LNPVLPHL-03230166126",  [from Loan field]
  "receiptDateTime": "2023-04-04",   [business date]
  "businessPartnerType": "CS",       [hardcoded]
  "receiptMode": "PL",               [extracted from Particular field - Master driven]
  "receiptSubMode": "DIRECT",        [hardcoded]
  "instrumentNo": "ICICR42026061600581471",  [extracted from Particular field]
  "instrumentDate": "2023-04-04",    [business date or backdated]
  "issuingBankId": "59",             [hardcoded - UAT]
  "issuingMicrCode": "395002018",    [hardcoded]
  "issuingIfscCode": "SBIN0007443",  [hardcoded]
  "issuingBranch": "BHATTAR ROAD",   [hardcoded]
  "bankAccountNo": "30772694064",    [hardcoded]
  "receiptAmount": "20000",          [from Amt field]
  "defaultBranch": "63",             [hardcoded]
  "receiptPurpose": "INSTALLMEN",    [hardcoded]
  "depositBankId": "39",             [from Bank master - A/c No mapping]
  "depositBankAccount": "201001531757", [from Bank master mapping]
  "Status": "R",                      [hardcoded]
  "transactionRef": "ABHFL12334",    [system generated - unique]
  "ReceivedFrom": "AI-BOT",          [hardcoded]
  "autoKnockOff": "N"                [hardcoded]
}

Account Mapping Logic (Bank Number → Deposit Account):
- 726 → 201001531726
- 719 → 201001531719
- 757 → 201001531757
- 733 → 201001531733
- 740 → 201001531740
- 512 → 201000294512
- 521 → 201000294521
- 126 → 200999820126
- 275 → 201002601275
- 105 → 201002960105

Particular Field Parsing:
Example: R/ICICR42026061600581471/ICIC0000011/MULTI SPACE D/URGENT/UN7472260616193910

Extract:
- receiptMode: First character (R)
- instrumentNo: ICICR42026061600581471

Response:
{
  "operationStatus": "1",
  "operationMessage": "Operation Completed Successfully",
  "errorMsgReceipt": [
    {
      "errorMsg": "",
      "loanNo": "LNMUMPHL-07210068228",
      "LoanId": "68228",
      "instrumentNo": "ICICR42026061600581471",
      "Status": "Approved",
      "errorCode": 1
    }
  ]
}

Receipt Modes:
- D = DD
- N = NEFT
- Q = Cheque
- R = RTGS
- U = UPI
- PL = Payment Lounge
- DIR = Cash
"""

TECHNICAL_SPECS = """
File Upload Requirements:
- Format: Excel (.xlsx)
- Fields required:
  * A/c No.
  * Bank Reference
  * Value Date
  * Type
  * Particular
  * Debit
  * Credit
  * Purpose
  * CRM
  * Date
  * Loan (mandatory)
  * Amt (mandatory)

Validation Rules:
1. Mandatory fields check
2. Duplicate loans detection
3. Invalid amount validation
4. Missing loan number check
5. Incorrect date format validation

API Processing:
1. One record at a time (sequential)
2. 3-second delay between API calls (MANDATORY)
3. Maintain processing logs
4. Store request and response

Auto Retry:
- Failed records retry every 3 hours
- Retry till configurable threshold
- Maintain retry history
- Log all retry attempts

Manual Retry:
- Users can view failed records
- Select records for manual retry
- Trigger immediate retry

Dashboard Requirements:
- Total Records
- Success count
- Failed count
- Pending count
- Processing status
- Retry count

Reports:
Success Report:
- Loan Number
- Receipt Amount
- Transaction Reference
- Receipt Status

Failure Report:
- Loan Number
- Error Message
- Error Code
- Retry Count
- Last Retry Date
"""

print("=" * 80)
print("🚀 BRD GENERATION QUALITY TEST")
print("=" * 80)

print("\n📊 INPUT DOCUMENTS:")
print(f"  1. Project Description: {len(PROJECT_DESC)} chars")
print(f"  2. Current Process: {len(CURRENT_PROCESS)} chars")
print(f"  3. Business Context: {len(BUSINESS_CONTEXT)} chars")
print(f"  4. API Specifications: {len(API_SPECS)} chars")
print(f"  5. Technical Specs: {len(TECHNICAL_SPECS)} chars")

print("\n" + "=" * 80)
print("🔄 STAGE 1: GENERATING IMPROVED BRD (Multi-Stage v2)")
print("=" * 80)

try:
    result = generate_brd_improved(
        project_description=PROJECT_DESC,
        current_process=CURRENT_PROCESS,
        business_context=BUSINESS_CONTEXT,
        api_specs=API_SPECS,
        technical_specs=TECHNICAL_SPECS
    )

    brd = result["brd"]
    issues = result["quality_issues"]

    print("\n✓ BRD Generated Successfully!")

    # Display results
    print("\n" + "=" * 80)
    print("📋 GENERATED BRD STRUCTURE")
    print("=" * 80)

    print(f"\n1. Executive Summary: {len(str(brd.get('executive_summary', '')))} chars")
    print(f"2. Business Objectives: {len(brd.get('business_objectives', []))} items")
    print(f"3. Functional Requirements: {len(brd.get('functional_requirements', []))} FRs")
    print(f"4. Non-Functional Requirements: {len(brd.get('non_functional_requirements', []))} NFRs")
    print(f"5. Integration Requirements: {len(brd.get('integration_requirements', []))} integrations")
    print(f"6. Business Rules: {len(brd.get('business_rules_and_validations', []))} rules")
    print(f"7. Error Handling: {len(brd.get('error_handling_and_exceptions', []))} scenarios")
    print(f"8. Reports: {len(brd.get('reporting_and_analytics', []))} reports")
    print(f"9. Project Phases: {len(brd.get('project_phases', []))} phases")
    print(f"10. Effort Estimation: {brd.get('effort_estimation', {}).get('total_hours', 0)} hours")
    print(f"11. Risks: {len(brd.get('risks_and_mitigations', []))} risks")
    print(f"12. Success Criteria: {len(brd.get('success_criteria', []))} criteria")

    # Quality check
    print("\n" + "=" * 80)
    print("🔍 QUALITY VALIDATION RESULTS")
    print("=" * 80)

    if issues:
        print("\n⚠️ Issues Found:")
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print("\n✅ ALL QUALITY CHECKS PASSED!")
        print("   ✓ Minimum 10+ Functional Requirements")
        print("   ✓ Detailed acceptance criteria per FR")
        print("   ✓ 5+ Non-Functional Requirements")
        print("   ✓ All required sections populated")

    # Show sample FRs
    print("\n" + "=" * 80)
    print("📌 SAMPLE FUNCTIONAL REQUIREMENTS")
    print("=" * 80)

    frs = brd.get("functional_requirements", [])
    for i, fr in enumerate(frs[:3]):  # Show first 3
        print(f"\n{fr.get('id', 'N/A')}: {fr.get('title', 'N/A')}")
        print(f"  Priority: {fr.get('priority', 'N/A')}")
        print(f"  Description: {fr.get('description', 'N/A')[:100]}...")
        print(f"  Acceptance Criteria: {len(fr.get('acceptance_criteria', []))} items")
        if fr.get('business_rules'):
            print(f"  Business Rules: {fr.get('business_rules')[:80]}...")

    # Save to file for comparison
    print("\n" + "=" * 80)
    print("💾 SAVING RESULTS")
    print("=" * 80)

    with open("brd_generated_v2.json", "w") as f:
        json.dump(brd, f, indent=2)
    print("✓ Saved to: brd_generated_v2.json")

    with open("brd_quality_report.txt", "w") as f:
        f.write("BRD QUALITY REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total Functional Requirements: {len(frs)}\n")
        f.write(f"Total Non-Functional Requirements: {len(brd.get('non_functional_requirements', []))}\n")
        f.write(f"Total Business Rules: {len(brd.get('business_rules_and_validations', []))}\n")
        f.write(f"Total Error Scenarios: {len(brd.get('error_handling_and_exceptions', []))}\n")
        f.write(f"Total Risks: {len(brd.get('risks_and_mitigations', []))}\n")
        f.write(f"Total Success Criteria: {len(brd.get('success_criteria', []))}\n\n")
        f.write(f"Quality Issues: {len(issues)}\n")
        if issues:
            for issue in issues:
                f.write(f"  - {issue}\n")

    print("✓ Saved to: brd_quality_report.txt")

except Exception as e:
    print(f"\n❌ Error generating BRD: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("✅ TEST COMPLETE")
print("=" * 80)
print("\nNEXT STEPS:")
print("1. Compare brd_generated_v2.json with ChatGPT and Copilot BRDs")
print("2. Check for:")
print("   - Number of FRs (should be 10+)")
print("   - Detailed acceptance criteria")
print("   - Specific API mappings")
print("   - Business logic detail")
print("3. Measure accuracy improvement")
