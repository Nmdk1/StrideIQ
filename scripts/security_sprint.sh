#!/bin/bash
# ============================================================================
# Security Sprint Loop: implement -> test -> judge -> advance
# ============================================================================
#
# This script implements security fixes in phases, with rigorous testing
# at each step before advancing.
#
# PHASES:
#   Phase 0: Critical auth fixes (LOW RISK - won't break site)
#   Phase 1: Critical security fixes (LOW-MEDIUM RISK)
#   Phase 2: High priority fixes (MEDIUM RISK)
#   Phase 3: Breaking changes (HIGH RISK - requires user notification)
#
# Usage:
#   ./scripts/security_sprint.sh [phase_number]
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_phase() {
    echo -e "${BLUE}=== PHASE $1: $2 ===${NC}"
}

echo_step() {
    echo -e "${YELLOW}>>> $1${NC}"
}

echo_pass() {
    echo -e "${GREEN}✓ $1 PASSED${NC}"
}

echo_fail() {
    echo -e "${RED}✗ $1 FAILED${NC}"
}

# ============================================================================
# PHASE 0: Critical Auth Fixes (LOW RISK)
# These add authentication to unauthenticated endpoints.
# Frontend already sends tokens, so this should NOT break anything.
# ============================================================================

PHASE_0_CHANGES=(
    "body_composition_auth"
    "work_pattern_auth"
    "nutrition_auth"
    "feedback_auth"
    "strava_token_encryption_fix"
    "token_encryption_key_failhard"
)

PHASE_0_TESTS=(
    "tests/test_security_auth_required.py"
)

# ============================================================================
# PHASE 1: Critical Security Fixes (LOW-MEDIUM RISK)
# ============================================================================

PHASE_1_CHANGES=(
    "v1_mark_race_auth"
    "v1_backfill_auth"
    "strava_webhook_signature_mandatory"
    "knowledge_vdot_auth"
    "gdpr_deletion_complete"
)

PHASE_1_TESTS=(
    "tests/test_security_phase1.py"
    "tests/test_phase8_security_golden_paths.py"
)

# ============================================================================
# PHASE 2: High Priority Fixes (MEDIUM RISK)
# ============================================================================

PHASE_2_CHANGES=(
    "sql_like_escape"
    "password_policy_strengthen"
    "password_reset_single_use"
    "jwt_claims_iat_jti"
    "file_upload_content_validation"
    "oauth_state_required"
    "rate_limit_auth_endpoints"
    "account_lockout_redis"
)

PHASE_2_TESTS=(
    "tests/test_security_phase2.py"
    "tests/test_phase8_token_jwt_invariants.py"
)

# ============================================================================
# PHASE 3: Breaking Changes (HIGH RISK - Requires Coordination)
# These will log out users or require infrastructure changes.
# Deploy during low-traffic window with user notification.
# ============================================================================

PHASE_3_CHANGES=(
    "jwt_expiration_reduce_7d"
    "refresh_token_implementation"
    "docker_nonroot_user"
    "database_ssl_require"
    "redis_authentication"
    "frontend_security_headers"
    "caddy_security_headers"
)

PHASE_3_TESTS=(
    "tests/test_security_phase3.py"
    "tests/test_phase9_backend_smoke_golden_paths.py"
)

# ============================================================================
# Test Runner Function
# ============================================================================

run_tests() {
    local test_files=("$@")
    local all_passed=true
    
    echo_step "Running test suite..."
    
    for test_file in "${test_files[@]}"; do
        echo "  Testing: $test_file"
        
        if [ -f "apps/api/$test_file" ]; then
            if pytest "apps/api/$test_file" -v --tb=short 2>&1 | tee test_output.txt; then
                echo_pass "$test_file"
            else
                echo_fail "$test_file"
                echo ""
                echo "Failures:"
                grep -A5 "FAILED" test_output.txt || true
                all_passed=false
            fi
        else
            echo -e "${YELLOW}  (test file not yet created: $test_file)${NC}"
        fi
    done
    
    # Always run existing smoke tests to ensure no regressions
    echo_step "Running regression tests..."
    if pytest apps/api/tests/test_phase9_backend_smoke_golden_paths.py -v --tb=short 2>&1; then
        echo_pass "Regression tests"
    else
        echo_fail "Regression tests"
        all_passed=false
    fi
    
    if $all_passed; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Deployment Function
# ============================================================================

deploy_to_staging() {
    echo_step "Deploying to staging..."
    
    # Git operations
    git add -A
    git status
    
    read -p "Commit message: " commit_msg
    git commit -m "$commit_msg"
    
    # Push to staging branch
    git push origin HEAD:staging
    
    echo_pass "Deployed to staging"
}

deploy_to_production() {
    echo_step "Deploying to production..."
    
    read -p "Are you sure you want to deploy to production? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Deployment cancelled."
        return 1
    fi
    
    git push origin HEAD:main
    
    echo_pass "Deployed to production"
}

# ============================================================================
# Main Sprint Loop
# ============================================================================

sprint_phase() {
    local phase=$1
    local -n changes_ref=$2
    local -n tests_ref=$3
    
    echo_phase "$phase" "Starting security sprint"
    echo ""
    echo "Changes to implement:"
    for change in "${changes_ref[@]}"; do
        echo "  - $change"
    done
    echo ""
    
    for change in "${changes_ref[@]}"; do
        echo ""
        echo -e "${BLUE}=== IMPLEMENTING: $change ===${NC}"
        echo ""
        
        while true; do
            # Prompt for implementation
            echo "Implement '$change' now, then press Enter to run tests..."
            read -p "(or type 'skip' to skip this change): " action
            
            if [ "$action" == "skip" ]; then
                echo "Skipping $change"
                break
            fi
            
            # Run tests
            if run_tests "${tests_ref[@]}"; then
                echo_pass "$change"
                break
            else
                echo_fail "$change - analyzing..."
                echo ""
                echo "Tests failed. Options:"
                echo "  1. Fix and press Enter to retry"
                echo "  2. Type 'skip' to skip this change"
                echo "  3. Type 'abort' to stop the sprint"
                read -p "Action: " action
                
                if [ "$action" == "skip" ]; then
                    echo "Skipping $change"
                    break
                elif [ "$action" == "abort" ]; then
                    echo "Sprint aborted."
                    exit 1
                fi
                # Otherwise, loop and retry
            fi
        done
    done
    
    echo ""
    echo_phase "$phase" "COMPLETE"
    echo ""
    
    # Deployment decision
    echo "Phase $phase implementation complete."
    echo "Options:"
    echo "  1. deploy-staging - Deploy to staging for manual testing"
    echo "  2. deploy-prod    - Deploy to production"
    echo "  3. continue       - Continue to next phase"
    echo "  4. stop           - Stop here"
    read -p "Action: " action
    
    case $action in
        deploy-staging)
            deploy_to_staging
            echo ""
            echo "Test on staging, then run this script again to continue."
            ;;
        deploy-prod)
            deploy_to_production
            ;;
        continue)
            echo "Continuing to next phase..."
            ;;
        stop)
            echo "Stopping. Run this script again to continue."
            exit 0
            ;;
    esac
}

# ============================================================================
# Entry Point
# ============================================================================

echo "=============================================="
echo "  StrideIQ Security Sprint"
echo "=============================================="
echo ""
echo "This script will guide you through implementing"
echo "security fixes in phases, with testing at each step."
echo ""
echo "Phases:"
echo "  0 - Critical auth fixes (LOW RISK)"
echo "  1 - Critical security fixes (LOW-MEDIUM RISK)"
echo "  2 - High priority fixes (MEDIUM RISK)"
echo "  3 - Breaking changes (HIGH RISK)"
echo ""

# Check if specific phase requested
if [ -n "$1" ]; then
    phase=$1
else
    read -p "Start from phase (0-3) [0]: " phase
    phase=${phase:-0}
fi

cd "$(dirname "$0")/.."  # Navigate to project root

case $phase in
    0)
        sprint_phase 0 PHASE_0_CHANGES PHASE_0_TESTS
        sprint_phase 1 PHASE_1_CHANGES PHASE_1_TESTS
        sprint_phase 2 PHASE_2_CHANGES PHASE_2_TESTS
        sprint_phase 3 PHASE_3_CHANGES PHASE_3_TESTS
        ;;
    1)
        sprint_phase 1 PHASE_1_CHANGES PHASE_1_TESTS
        sprint_phase 2 PHASE_2_CHANGES PHASE_2_TESTS
        sprint_phase 3 PHASE_3_CHANGES PHASE_3_TESTS
        ;;
    2)
        sprint_phase 2 PHASE_2_CHANGES PHASE_2_TESTS
        sprint_phase 3 PHASE_3_CHANGES PHASE_3_TESTS
        ;;
    3)
        sprint_phase 3 PHASE_3_CHANGES PHASE_3_TESTS
        ;;
    *)
        echo "Invalid phase: $phase"
        exit 1
        ;;
esac

echo ""
echo "=============================================="
echo "  ALL SPRINTS COMPLETE"
echo "=============================================="
