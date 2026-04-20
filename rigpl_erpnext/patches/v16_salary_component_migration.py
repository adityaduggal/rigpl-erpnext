# -*- coding: utf-8 -*-
"""
Migrate Salary Components from v12 is_contribution to v16 accrual_component

This patch:
1. Sets type='Earning' for components with is_contribution=1
2. Sets accrual_component=1 for components with is_contribution=1
3. Sets type based on is_earning/is_deduction for other components if type is not set

Run with: bench --site rigplerpnext.localhost execute rigpl_erpnext.patches.v16_salary_component_migration
"""
import frappe


def execute():
    """Migrate Salary Components from legacy is_contribution to v16 accrual_component"""
    
    print("\n" + "="*80)
    print("SALARY COMPONENT MIGRATION TO HRMS v16")
    print("="*80)
    
    # Check if custom fields exist
    has_is_contribution = frappe.db.exists("Custom Field", "Salary Component-is_contribution")
    has_is_earning = frappe.db.exists("Custom Field", "Salary Component-is_earning")
    has_is_deduction = frappe.db.exists("Custom Field", "Salary Component-is_deduction")
    
    if not any([has_is_contribution, has_is_earning, has_is_deduction]):
        print("\n✅ No legacy custom fields found - migration may have already been completed.")
        print("="*80 + "\n")
        return
    
    # Get all Salary Components
    components = frappe.db.sql("""
        SELECT name, type, is_earning, is_deduction, is_contribution, accrual_component
        FROM `tabSalary Component`
    """, as_dict=1)
    
    print(f"\nFound {len(components)} Salary Components to check.")
    
    migrated_count = 0
    type_fixed_count = 0
    
    for comp in components:
        updates = {}
        comp_name = comp["name"]
        
        # 1. Migrate is_contribution=1 to type='Earning' + accrual_component=1
        if comp.get("is_contribution") == 1:
            if comp.get("accrual_component") != 1:
                updates["accrual_component"] = 1
                print(f"  ✓ {comp_name}: Setting accrual_component=1 (was is_contribution=1)")
            
            if not comp.get("type") or comp.get("type") != "Earning":
                updates["type"] = "Earning"
                print(f"  ✓ {comp_name}: Setting type='Earning' (was is_contribution=1)")
            
            migrated_count += 1
        
        # 2. Fix type field based on is_earning/is_deduction if not set
        elif not comp.get("type"):
            if comp.get("is_earning") == 1:
                updates["type"] = "Earning"
                print(f"  ✓ {comp_name}: Setting type='Earning' (based on is_earning=1)")
                type_fixed_count += 1
            elif comp.get("is_deduction") == 1:
                updates["type"] = "Deduction"
                print(f"  ✓ {comp_name}: Setting type='Deduction' (based on is_deduction=1)")
                type_fixed_count += 1
        
        # Apply updates
        if updates:
            frappe.db.set_value("Salary Component", comp_name, updates, update_modified=False)
    
    # Commit the changes
    frappe.db.commit()
    
    print("\n" + "-"*80)
    print(f"Migration complete!")
    print(f"  - Components with is_contribution migrated to accrual_component: {migrated_count}")
    print(f"  - Components with type field fixed: {type_fixed_count}")
    print("="*80 + "\n")
    
    return {
        "migrated": migrated_count,
        "type_fixed": type_fixed_count
    }
