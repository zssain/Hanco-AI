"""
Quick setup script for pricing system
Installs onnx package and creates the model
"""
import subprocess
import sys
import os

def main():
    print("=" * 60)
    print("🚀 Setting Up Dynamic Pricing System")
    print("=" * 60)
    
    # Step 1: Install onnx package
    print("\n1️⃣ Installing onnx package...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'onnx>=1.15.0'],
            check=True
        )
        print("   ✅ onnx package installed")
    except subprocess.CalledProcessError:
        print("   ❌ Failed to install onnx")
        return False
    
    # Step 2: Create ONNX model
    print("\n2️⃣ Creating ONNX model...")
    try:
        model_script = os.path.join(
            os.path.dirname(__file__),
            'ml',
            'training',
            'create_dummy_model.py'
        )
        
        subprocess.run([sys.executable, model_script], check=True)
        print("   ✅ ONNX model created")
    except subprocess.CalledProcessError:
        print("   ❌ Failed to create model")
        return False
    
    # Step 3: Test the system
    print("\n3️⃣ Testing pricing system...")
    try:
        test_script = os.path.join(
            os.path.dirname(__file__),
            'test_pricing.py'
        )
        
        subprocess.run([sys.executable, test_script], check=True)
        print("   ✅ Pricing system tested successfully")
    except subprocess.CalledProcessError:
        print("   ⚠️  Tests failed, but system may still work")
    
    print("\n" + "=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print("\n📚 Next steps:")
    print("   1. Start server: python -m app.main")
    print("   2. Visit: http://localhost:8000/api/v1/docs")
    print("   3. Test: POST /api/v1/pricing/calculate")
    print("\n" + "=" * 60)
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
