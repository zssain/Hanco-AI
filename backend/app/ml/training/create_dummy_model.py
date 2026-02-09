"""
Create a dummy ONNX model for dynamic pricing
This generates a simple computational graph for testing without real training data
"""
import numpy as np
import onnx
from onnx import helper, TensorProto
import os

def create_dummy_pricing_model():
    """
    Creates a simple ONNX model that:
    - Accepts 10 numeric features
    - Computes: price = sum(features) × 0.1
    - Returns a single price value
    """
    
    # Define input tensor: shape [1, 10] (batch_size=1, features=10)
    input_features = helper.make_tensor_value_info(
        'input_features',
        TensorProto.FLOAT,
        [1, 10]
    )
    
    # Define output tensor: shape [1, 1]
    output_price = helper.make_tensor_value_info(
        'output_price',
        TensorProto.FLOAT,
        [1, 1]
    )
    
    # Create constant tensor for multiplication (0.1)
    multiplier = helper.make_tensor(
        'multiplier',
        TensorProto.FLOAT,
        [1],
        [0.1]
    )
    
    # Node 1: ReduceSum - sum all features along axis 1
    reduce_sum_node = helper.make_node(
        'ReduceSum',
        inputs=['input_features'],
        outputs=['sum_features'],
        axes=[1],
        keepdims=1
    )
    
    # Node 2: Mul - multiply sum by 0.1
    mul_node = helper.make_node(
        'Mul',
        inputs=['sum_features', 'multiplier'],
        outputs=['output_price']
    )
    
    # Create the graph
    graph_def = helper.make_graph(
        nodes=[reduce_sum_node, mul_node],
        name='DummyPricingModel',
        inputs=[input_features],
        outputs=[output_price],
        initializer=[multiplier]
    )
    
    # Create the model
    model_def = helper.make_model(
        graph_def,
        producer_name='hanco-ai',
        opset_imports=[helper.make_opsetid('', 14)]
    )
    
    # Check model validity
    onnx.checker.check_model(model_def)
    
    # Save the model
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, 'model.onnx')
    onnx.save(model_def, model_path)
    
    print(f"✅ Dummy ONNX model created successfully!")
    print(f"📁 Saved to: {os.path.abspath(model_path)}")
    print(f"📊 Model accepts 10 features and outputs a price")
    print(f"🧮 Formula: price = sum(features) × 0.1")
    
    # Test the model
    test_features()
    
    return model_path


def test_features():
    """Test the model with sample features"""
    import onnxruntime as ort
    
    model_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'models', 
        'model.onnx'
    )
    
    # Load model
    session = ort.InferenceSession(model_path)
    
    # Test with sample features
    # [rental_days, day_of_week, month, base_rate, temp, rain, wind, competitor_price, demand, bias]
    test_input = np.array([[5, 1, 12, 100, 25, 0, 10, 95, 0.5, 1]], dtype=np.float32)
    
    result = session.run(None, {'input_features': test_input})
    predicted_price = result[0][0][0]
    
    print(f"\n🧪 Test Inference:")
    print(f"   Input features sum: {test_input.sum()}")
    print(f"   Predicted price: ${predicted_price:.2f}")
    print(f"   Expected: ${test_input.sum() * 0.1:.2f}")


if __name__ == '__main__':
    print("=" * 60)
    print("🤖 Creating Dummy ONNX Pricing Model")
    print("=" * 60)
    create_dummy_pricing_model()
    print("\n" + "=" * 60)
    print("✨ Done! The model is ready for use.")
    print("=" * 60)


# ============================================================
# Run this ONCE to create the dummy ONNX model:
# 
# cd backend
# python app/ml/training/create_dummy_model.py
# 
# This will create: app/ml/models/model.onnx
# ============================================================
