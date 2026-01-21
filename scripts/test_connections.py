#!/usr/bin/env python3
"""Test S3 and Procore database connections."""

import asyncio
import os
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()


def test_s3_connection():
    """Test S3 bucket access."""
    print("\n" + "=" * 60)
    print("S3 CONNECTION TEST")
    print("=" * 60)

    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3")
        return False

    bucket_name = os.environ.get("S3_BUCKET", "procore-integration-files")
    region = os.environ.get("AWS_REGION", "us-east-1")

    print(f"Bucket: {bucket_name}")
    print(f"Region: {region}")

    try:
        s3 = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )

        # Test 1: Check bucket exists and we have access
        print("\n[1] Testing bucket access...")
        s3.head_bucket(Bucket=bucket_name)
        print("    Bucket exists and accessible")

        # Test 2: List objects (limit to 5)
        print("\n[2] Listing objects (first 5)...")
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=5)

        if "Contents" in response:
            for obj in response["Contents"]:
                print(f"    - {obj['Key']} ({obj['Size']} bytes)")
            print(f"    Total objects in bucket: {response.get('KeyCount', 'unknown')}")
        else:
            print("    Bucket is empty or no list permission")

        print("\nS3 CONNECTION: SUCCESS")
        return True

    except NoCredentialsError:
        print("\nERROR: AWS credentials not found")
        print("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env")
        return False
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        print(f"\nERROR: {error_code} - {error_msg}")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        return False


@pytest.mark.asyncio
async def test_procore_db_connection():
    """Test Procore database connection."""
    print("\n" + "=" * 60)
    print("PROCORE DATABASE CONNECTION TEST")
    print("=" * 60)

    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed. Run: pip install asyncpg")
        return False

    db_url = os.environ.get("PROCORE_DATABASE_URL")

    if not db_url:
        print("ERROR: PROCORE_DATABASE_URL not set in environment")
        return False

    # Mask password in output
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    masked_url = f"{parsed.scheme}://{parsed.username}:****@{parsed.hostname}:{parsed.port}{parsed.path}"
    print(f"URL: {masked_url}")

    try:
        # Test 1: Connect
        print("\n[1] Testing connection...")
        conn = await asyncpg.connect(db_url)
        print("    Connected successfully")

        # Test 2: Check version
        print("\n[2] Database version...")
        version = await conn.fetchval("SELECT version()")
        print(f"    {version[:60]}...")

        # Test 3: List tables
        print("\n[3] Listing tables (first 10)...")
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            LIMIT 10
        """)
        for t in tables:
            print(f"    - {t['table_name']}")

        # Test 4: Check read-only (attempt a harmless write that should fail)
        print("\n[4] Verifying read-only access...")
        try:
            await conn.execute("CREATE TEMP TABLE _connection_test (id int)")
            await conn.execute("DROP TABLE _connection_test")
            print("    WARNING: User has write permissions (not read-only)")
        except asyncpg.InsufficientPrivilegeError:
            print("    Confirmed read-only access")
        except Exception as e:
            print(f"    Could not verify: {e}")

        await conn.close()
        print("\nPROCORE DATABASE CONNECTION: SUCCESS")
        return True

    except asyncpg.InvalidPasswordError:
        print("\nERROR: Invalid password")
        return False
    except asyncpg.InvalidCatalogNameError:
        print("\nERROR: Database does not exist")
        return False
    except OSError as e:
        print(f"\nERROR: Cannot connect to host - {e}")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        return False


async def main():
    """Run all connection tests."""
    print("\n" + "#" * 60)
    print("# CONNECTION TESTS")
    print("#" * 60)

    results = {}

    # Test S3
    results["S3"] = test_s3_connection()

    # Test Procore DB
    results["Procore DB"] = await test_procore_db_connection()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    # Exit with error if any failed
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
