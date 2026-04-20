# -*- coding: utf-8 -*-
"""
Check Salary Component Migration Status

Run with: bench --site rigplerpnext.localhost execute rigpl_erpnext.patches.check_salary_component_status
"""
import frappe


def execute():
    """Check if Salary Components need migration from is_contribution to accrual_component"""
    
    print("\n" + "="*80)
    print("SALARY COMPONENT MIGRATION STATUS CHECK")
    print("="*80)
    
    # Check if custom fields exist
    has_is_contribution = frappe.db.exists("Custom Field", "Salary Component-is_contribution")
    has_is_earning = frappe.db.exists("Custom Field", "Salary Component-is_earning")
    has_is_deduction = frappe.db.exists("Custom Field", "Salary Component-is_deduction")
    
    print(f"\nCustom Fields Status:")
    print(f"  - is_contribution field exists: {bool(has_is_contribution)}")
    print(f"  - is_earning field exists: {bool(has_is_earning)}")
    print(f"  - is_deduction field exists: {bool(has_is_deduction)}")
    
    # Get all Salary Components and their field values
    components = frappe.db.sql("""
        SELECT 
            name, 
            type,
            is_earning,
            is_deduction,
            is_contribution,
            accrual_component
        FROM `tabSalary Component`
        ORDER BY name
    """, as_dict=1)
    
    print(f"\n\nTotal Salary Components: {len(components)}")
    print("-"*80)
    
    # Categorize components
    needs_migration = []
    already_migrated = []
    
    for comp in components:
        # Check if it's a legacy contribution that needs migration
        if comp.get("is_contribution") == 1 and comp.get("accrual_component") != 1:
            needs_migration.append(comp)
        elif comp.get("is_contribution") == 1 and comp.get("accrual_component") == 1:
            already_migrated.append(comp)
    
    print(f"\nComponents with is_contribution=1 needing migration: {len(needs_migration)}")
    for comp in needs_migration:
        print(f"  - {comp['name']}: type={comp.get('type')}, accrual_component={comp.get('accrual_component')}")
    
    print(f"\nComponents already migrated (is_contribution=1 AND accrual_component=1): {len(already_migrated)}")
    for comp in already_migrated:
        print(f"  - {comp['name']}: type={comp.get('type')}")
    
    # Show all components for reference
    print(f"\n\nAll Salary Components:")
    print("-"*80)
    print(f"{'Name':<40} {'Type':<12} {'is_earn':<8} {'is_ded':<8} {'is_cont':<8} {'accrual':<8}")
    print("-"*80)
    for comp in components:
        print(f"{comp['name'][:39]:<40} {str(comp.get('type') or '')[:11]:<12} {comp.get('is_earning') or 0:<8} {comp.get('is_deduction') or 0:<8} {comp.get('is_contribution') or 0:<8} {comp.get('accrual_component') or 0:<8}")
    
    print("\n" + "="*80)
    
    if needs_migration:
        print("\n⚠️  MIGRATION NEEDED: Run the migration patch to update these components.")
    else:
        print("\n✅ No migration needed - all components are already properly configured.")
    
    print("="*80 + "\n")
    
    return {
        "needs_migration": len(needs_migration),
        "already_migrated": len(already_migrated),
        "total": len(components)
    }
