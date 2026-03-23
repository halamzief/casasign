#!/usr/bin/env python3
"""
Clean duplicate email templates via the admin API endpoint.

Uses the working API instead of direct database access.
"""

import asyncio
from collections import defaultdict
from datetime import datetime

import httpx
from loguru import logger

API_BASE_URL = "http://localhost:9001"


async def get_all_templates() -> list[dict]:
    """Fetch all templates via API."""
    logger.info("Fetching templates via API...")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/api/admin/templates")
        response.raise_for_status()
        templates = response.json()

    logger.info(f"Found {len(templates)} templates")
    return templates


def group_templates_by_key(templates: list[dict]) -> dict[tuple, list[dict]]:
    """Group templates by (template_key, language, tenant_id)."""
    grouped = defaultdict(list)

    for template in templates:
        key = (template["template_key"], template.get("language", "de"), template.get("tenant_id"))
        grouped[key].append(template)

    return grouped


def identify_duplicates(grouped: dict[tuple, list[dict]]) -> dict[tuple, dict]:
    """Identify duplicate templates."""
    duplicates = {}

    for key, templates in grouped.items():
        if len(templates) > 1:
            # Sort by created_at (oldest first)
            sorted_templates = sorted(
                templates,
                key=lambda t: datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
            )

            duplicates[key] = {
                "keep": sorted_templates[0],  # Keep oldest
                "delete": sorted_templates[1:],  # Delete newer ones
            }

    return duplicates


def print_duplicate_report(duplicates: dict[tuple, dict]) -> None:
    """Print detailed report of duplicates."""
    if not duplicates:
        logger.info("✅ No duplicates found!")
        return

    logger.warning(f"⚠️  Found {len(duplicates)} groups of duplicates")

    total_to_delete = sum(len(d["delete"]) for d in duplicates.values())
    logger.warning(f"📊 Total templates to delete: {total_to_delete}")

    print("\n" + "=" * 80)
    print("DUPLICATE TEMPLATES REPORT")
    print("=" * 80)

    for key, data in duplicates.items():
        template_key, language, tenant_id = key
        keep = data["keep"]
        delete_list = data["delete"]

        print(f"\n📝 Template Key: {template_key} (language={language}, tenant_id={tenant_id})")
        print(f"   Total instances: {len(delete_list) + 1}")

        print("\n   ✅ KEEP (oldest):")
        print(f"      ID: {keep['id']}")
        print(f"      Name: {keep['name']}")
        print(f"      Created: {keep['created_at']}")
        print(f"      is_default: {keep['is_default']}")
        print(f"      is_active: {keep['is_active']}")

        print(f"\n   ❌ DELETE ({len(delete_list)} duplicates):")
        for i, template in enumerate(delete_list, 1):
            print(f"      {i}. ID: {template['id']}")
            print(f"         Created: {template['created_at']}")
            print(f"         is_active: {template['is_active']}")

    print("\n" + "=" * 80)


async def delete_template(template_id: str) -> bool:
    """Delete a template via API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{API_BASE_URL}/api/admin/templates/{template_id}")
            response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to delete {template_id}: {e}")
        return False


async def clean_duplicates(duplicates: dict[tuple, dict], execute: bool = False) -> None:
    """Clean duplicate templates."""
    if not duplicates:
        logger.info("✅ No duplicates to clean")
        return

    if not execute:
        logger.warning("🔍 DRY RUN MODE - No changes will be made")
        logger.warning("   Add --execute flag to actually delete duplicates")
        return

    logger.info("🗑️  Starting cleanup (EXECUTE MODE)...")

    total_deleted = 0
    total_failed = 0

    for key, data in duplicates.items():
        template_key, language, tenant_id = key
        delete_list = data["delete"]

        logger.info(f"Processing {template_key} ({len(delete_list)} duplicates)...")

        for template in delete_list:
            template_id = template["id"]

            success = await delete_template(template_id)

            if success:
                logger.success(f"  ✅ Deleted template {template_id}")
                total_deleted += 1
            else:
                logger.error(f"  ❌ Failed to delete {template_id}")
                total_failed += 1

    logger.info("\n📊 Cleanup Summary:")
    logger.info(f"   ✅ Successfully deleted: {total_deleted}")
    logger.info(f"   ❌ Failed: {total_failed}")


async def main():
    """Main execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Clean duplicate email templates")
    parser.add_argument(
        "--execute", action="store_true", help="Actually delete duplicates (default is dry-run)"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("EMAIL TEMPLATE DUPLICATE CLEANER (API MODE)")
    logger.info("=" * 80)

    # Fetch all templates
    templates = await get_all_templates()

    # Group by key
    grouped = group_templates_by_key(templates)
    logger.info(f"Grouped into {len(grouped)} unique template keys")

    # Identify duplicates
    duplicates = identify_duplicates(grouped)

    # Print report
    print_duplicate_report(duplicates)

    # Clean duplicates
    await clean_duplicates(duplicates, execute=args.execute)

    if not args.execute and duplicates:
        logger.warning("\n💡 To actually delete duplicates, run with --execute flag:")
        logger.warning("   python scripts/clean_duplicates_via_api.py --execute")


if __name__ == "__main__":
    asyncio.run(main())
