import asyncio
import json
from dotenv import load_dotenv

load_dotenv(".env")

from backend.agents.coordinator import run_pipeline
from backend.models import UserProfile


profile = UserProfile(
    age=35,
    gender="male",
    state="uttar pradesh",
    residence="rural",
    annual_income=100000,
    category="general",
    occupation="farmer",
    education_level="ug",
    has_bpl_card=True,
    owns_cultivable_land=True,
    owns_pucca_house=False,
    has_bank_account=True,
    has_lpg_connection=False,
    income_tax_payer=False,
    government_employee=False,
    extra_info=(
        "I am a farmer and I want financial support for a solar pump "
        "to irrigate my agricultural land."
    ),
)


async def main():
    print("\n========== FULL PIPELINE TEST ==========\n")

    async for raw_event in run_pipeline(profile):
        event = json.loads(raw_event.removeprefix("data: ").strip())

        if event["type"] == "agent":
            print(
                f"[{event['agent']}] "
                f"{event['message']}"
            )

        elif event["type"] == "findings":
            print("\n========== FINAL FINDINGS ==========\n")

            print("SUMMARY:")
            print(event["summary"])

            print("\nSCHEMES:")
            for finding in event["findings"]:
                print(
                    f"- {finding['name']}: "
                    f"{finding['status']}"
                )

                if finding["reasons"]:
                    print(f"  Reason: {finding['reasons']}")

                if finding["unknown_fields"]:
                    print(
                        f"  Unknown: "
                        f"{finding['unknown_fields']}"
                    )

            print("\nDOCUMENT CHECKLIST:")
            for item in event["checklist"]:
                print(item)

    print("\n========== TEST COMPLETE ==========\n")


if __name__ == "__main__":
    asyncio.run(main())