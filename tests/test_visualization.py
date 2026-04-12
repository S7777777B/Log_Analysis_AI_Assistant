"""
可视化模块测试脚本
测试 dashboard.py 中的各个功能函数
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_dashboard_imports():
    """测试仪表板模块导入"""
    print("测试 1: 导入 dashboard 模块...")
    try:
        from src.visualization import dashboard
        print("✅ dashboard 模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ dashboard 模块导入失败：{e}")
        return False


def test_function_existence():
    """测试所有功能函数是否存在"""
    print("\n测试 2: 检查功能函数是否存在...")
    try:
        from src.visualization.dashboard import (
            create_dashboard,
            show_realtime_logs,
            show_ueba_ranking,
            show_security_score,
            show_ai_suggestions,
            show_history_search
        )
        print("✅ 所有功能函数存在")
        return True
    except ImportError as e:
        print(f"❌ 功能函数缺失：{e}")
        return False


def test_show_security_score():
    """测试安全评分看板函数"""
    print("\n测试 3: 测试 show_security_score 函数...")
    try:
        from src.visualization.dashboard import show_security_score
        print("⚠️  show_security_score 需要在 Streamlit 环境中测试")
        print("✅ 函数定义正常")
        return True
    except Exception as e:
        print(f"❌ show_security_score 测试失败：{e}")
        return False


def test_show_ueba_ranking():
    """测试 UEBA 异常排行函数"""
    print("\n测试 4: 测试 show_ueba_ranking 函数...")
    try:
        from src.visualization.dashboard import show_ueba_ranking
        print("⚠️  show_ueba_ranking 需要在 Streamlit 环境中测试")
        print("✅ 函数定义正常")
        return True
    except Exception as e:
        print(f"❌ show_ueba_ranking 测试失败：{e}")
        return False


def test_show_ai_suggestions():
    """测试 AI 处置建议函数"""
    print("\n测试 5: 测试 show_ai_suggestions 函数...")
    try:
        from src.visualization.dashboard import show_ai_suggestions
        print("⚠️  show_ai_suggestions 需要在 Streamlit 环境中测试")
        print("✅ 函数定义正常")
        return True
    except Exception as e:
        print(f"❌ show_ai_suggestions 测试失败：{e}")
        return False


def test_show_realtime_logs():
    """测试实时日志流函数"""
    print("\n测试 6: 测试 show_realtime_logs 函数...")
    try:
        from src.visualization.dashboard import show_realtime_logs
        print("⚠️  show_realtime_logs 需要在 Streamlit 环境中测试")
        print("✅ 函数定义正常")
        return True
    except Exception as e:
        print(f"❌ show_realtime_logs 测试失败：{e}")
        return False


def test_show_history_search():
    """测试历史查询函数"""
    print("\n测试 7: 测试 show_history_search 函数...")
    try:
        from src.visualization.dashboard import show_history_search
        print("⚠️  show_history_search 需要在 Streamlit 环境中测试")
        print("✅ 函数定义正常")
        return True
    except Exception as e:
        print(f"❌ show_history_search 测试失败：{e}")
        return False


def test_dashboard_structure():
    """测试仪表板结构"""
    print("\n测试 8: 测试仪表板结构...")
    try:
        from src.visualization.dashboard import create_dashboard
        import inspect
        
        # 检查函数签名
        sig = inspect.signature(create_dashboard)
        print(f"✅ create_dashboard 函数签名：{sig}")
        
        # 检查源代码
        source = inspect.getsource(create_dashboard)
        if "st.sidebar.selectbox" in source:
            print("✅ 侧边栏导航存在")
        else:
            print("⚠️  侧边栏导航可能缺失")
        
        return True
    except Exception as e:
        print(f"❌ 仪表板结构测试失败：{e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("可视化模块测试套件")
    print("=" * 60)
    
    tests = [
        test_dashboard_imports,
        test_function_existence,
        test_show_security_score,
        test_show_ueba_ranking,
        test_show_ai_suggestions,
        test_show_realtime_logs,
        test_show_history_search,
        test_dashboard_structure
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ 测试 {test.__name__} 异常：{e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"通过：{passed}/{total}")
    print(f"成功率：{passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
