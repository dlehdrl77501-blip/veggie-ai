import streamlit as st
import sqlite3
import json

st.set_page_config(page_title="야채즙 AI", page_icon="🥦", layout="centered")

st.title("🥬 야채즙 AI 분석기")
st.write("야채를 입력하거나 AI 추천을 받아 영양소, 건강 효과, 맛, 부족 영양소, 즐겨찾기까지 분석/저장할 수 있습니다!")

# --- DB 함수 및 테이블 생성 ---
def init_db():
    conn = sqlite3.connect("veggie_ai.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        recipe_name TEXT,
        ingredients TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

init_db()

# --- 즐겨찾기 저장 함수 ---
def save_favorite(user_id, recipe_name, ingredients_dict):
    conn = sqlite3.connect("veggie_ai.db")
    cursor = conn.cursor()
    ingredients_str = json.dumps(ingredients_dict, ensure_ascii=False)
    cursor.execute("INSERT INTO Favorites (user_id, recipe_name, ingredients) VALUES (?, ?, ?)",
                   (user_id, recipe_name, ingredients_str))
    conn.commit()
    conn.close()

# --- 즐겨찾기 목록 불러오기 ---
def get_favorites(user_id):
    conn = sqlite3.connect("veggie_ai.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, recipe_name, ingredients, created_at FROM Favorites WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- 즐겨찾기 삭제 ---
def delete_favorite(fav_id):
    conn = sqlite3.connect("veggie_ai.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Favorites WHERE id = ?", (fav_id,))
    conn.commit()
    conn.close()

# --- 입력 파싱 ---
def parse_input(text):
    lines = text.strip().splitlines()
    result = {}
    for line in lines:
        try:
            name, gram = line.strip().split()
            result[name] = float(gram)
        except:
            continue
    return result

# --- 영양 분석 ---
def analyze_ingredients(ingredients):
    conn = sqlite3.connect("veggie_ai.db")
    cursor = conn.cursor()
    total_nutrients = {}
    effects = set()

    for veg_name, grams in ingredients.items():
        cursor.execute("SELECT id FROM Vegetables WHERE name_ko = ?", (veg_name,))
        row = cursor.fetchone()
        if not row:
            continue
        veg_id = row[0]
        # 영양소
        cursor.execute("SELECT nutrient_name, amount_per_100g FROM Nutrients WHERE vegetable_id = ?", (veg_id,))
        for nutrient, amount in cursor.fetchall():
            total_nutrients[nutrient] = total_nutrients.get(nutrient, 0) + amount * grams / 100
        # 수분
        cursor.execute("SELECT water_content FROM FlavorProfile WHERE vegetable_id = ?", (veg_id,))
        wc = cursor.fetchone()
        if wc and wc[0] is not None:
            total_nutrients["수분"] = total_nutrients.get("수분", 0) + wc[0] * grams / 100

    # 건강 효과
    for nutrient in total_nutrients:
        cursor.execute("SELECT health_effect FROM HealthEffects WHERE nutrient_name = ?", (nutrient,))
        for row in cursor.fetchall():
            effects.update([e.strip() for e in row[0].split(",")])

    conn.close()
    return total_nutrients, list(effects)

# --- 부족 영양소 보완 제안 ---
def suggest_additional_veggies(nutrient_totals):
    suggestions = []
    if nutrient_totals.get("비타민 C", 0) < 30:
        suggestions.append("💡 레몬 or 브로콜리 추가 → 비타민 C 강화")
    if nutrient_totals.get("수분", 0) < 70:
        suggestions.append("💧 오이 추가 → 수분 보충")
    if nutrient_totals.get("베타카로틴", 0) < 2000:
        suggestions.append("🥕 당근 추가 → 항산화 및 눈 건강 보완")
    return suggestions

# --- 맛 밸런스 평가 ---
def evaluate_flavor(ingredients):
    conn = sqlite3.connect("veggie_ai.db")
    cursor = conn.cursor()
    total = {"sweetness": 0, "bitterness": 0, "earthiness": 0}
    total_weight = 0
    for veg_name, grams in ingredients.items():
        cursor.execute("SELECT id FROM Vegetables WHERE name_ko = ?", (veg_name,))
        row = cursor.fetchone()
        if not row:
            continue
        veg_id = row[0]
        cursor.execute("SELECT sweetness, bitterness, earthiness FROM FlavorProfile WHERE vegetable_id = ?", (veg_id,))
        flavor = cursor.fetchone()
        if not flavor:
            continue
        sw, bt, ea = flavor
        total["sweetness"] += sw * grams
        total["bitterness"] += bt * grams
        total["earthiness"] += ea * grams
        total_weight += grams

    conn.close()

    if total_weight == 0:
        return "맛 정보 없음"

    avg = {k: round(v / total_weight, 2) for k, v in total.items()}
    return f"맛 밸런스 ▶ 단맛 {avg['sweetness']} / 쓴맛 {avg['bitterness']} / 흙맛 {avg['earthiness']}"

# --- AI 자동 조합 추천 ---
function_to_ingredients = {
    "피로 회복": ["브로콜리", "레몬", "시금치"],
    "눈 건강": ["당근", "시금치", "브로콜리"],
    "해독/디톡스": ["케일", "오이", "비트"],
    "혈액순환": ["비트", "셀러리", "사과"],
    "피부 개선": ["케일", "브로콜리", "오이"]
}

def recommend_recipe_for(goal):
    ingredients = function_to_ingredients.get(goal, [])
    return {veg: 30 for veg in ingredients}  # 기본 30g씩 배정

# --- 사용자 ID (예시) ---
USER_ID = "user_001"

# --- 탭 UI ---
tabs = st.tabs(["🔬 영양 분석", "💡 AI 추천", "⭐ 즐겨찾기"])

# --- 1. 영양 분석 탭 ---
with tabs[0]:
    st.subheader("야채와 양 입력 (예: 당근 40, 케일 20)")
    user_input = st.text_area("야채와 양 입력", "당근 40\n케일 20", key="input_text")
    ingredients = parse_input(user_input)
    if st.button("🔍 분석하기", key="analyze_btn"):
        nutrients, effects = analyze_ingredients(ingredients)
        st.subheader("🔬 분석된 영양소")
        if nutrients:
            for k, v in nutrients.items():
                st.write(f"- {k}: {v:.2f}")
        else:
            st.write("영양소 정보가 없습니다.")

        st.subheader("💪 건강 효과")
        if effects:
            for eff in effects:
                st.write(f"✅ {eff}")
        else:
            st.write("건강 효과 정보가 없습니다.")

        st.subheader("🧠 보완 제안")
        suggestions = suggest_additional_veggies(nutrients)
        if suggestions:
            for s in suggestions:
                st.write(s)
        else:
            st.write("🎉 좋은 균형입니다!")

        st.subheader("👅 맛 평가")
        st.write(evaluate_flavor(ingredients))

        # 즐겨찾기 저장
        recipe_name = st.text_input("레시피 이름을 입력하세요", "맞춤 야채즙", key="fav_name1")
        if st.button("⭐ 즐겨찾기 저장", key="fav_btn1"):
            save_favorite(USER_ID, recipe_name, ingredients)
            st.success("저장 완료!")

# --- 2. AI 추천 탭 ---
with tabs[1]:
    st.subheader("원하는 건강 기능을 선택하세요")
    goal = st.selectbox("건강 기능", list(function_to_ingredients.keys()), key="goal_select")
    if st.button("💡 AI 레시피 추천받기", key="ai_btn"):
        rec = recommend_recipe_for(goal)
        st.write("추천 조합:")
        for k, v in rec.items():
            st.write(f"- {k}: {v}g")
        st.session_state["ai_recipe"] = rec

    # 추천 조합 분석/저장
    if "ai_recipe" in st.session_state:
        st.subheader("🔬 추천 조합 영양 분석")
        nutrients, effects = analyze_ingredients(st.session_state["ai_recipe"])
        for k, v in nutrients.items():
            st.write(f"- {k}: {v:.2f}")
        st.subheader("💪 건강 효과")
        for eff in effects:
            st.write(f"✅ {eff}")
        st.subheader("👅 맛 평가")
        st.write(evaluate_flavor(st.session_state["ai_recipe"]))
        recipe_name2 = st.text_input("레시피 이름을 입력하세요", f"{goal}용 야채즙", key="fav_name2")
        if st.button("⭐ 즐겨찾기 저장", key="fav_btn2"):
            save_favorite(USER_ID, recipe_name2, st.session_state["ai_recipe"])
            st.success("저장 완료!")

# --- 3. 즐겨찾기 탭 ---
with tabs[2]:
    st.subheader("⭐ 나의 즐겨찾기 레시피")
    favs = get_favorites(USER_ID)
    if not favs:
        st.write("저장된 즐겨찾기가 없습니다.")
    else:
        for fav in favs:
            fid, name, ingr_str, created = fav
            ingr = json.loads(ingr_str)
            with st.expander(f"{name} ({created[:16]})"):
                st.write("재료:")
                for k, v in ingr.items():
                    st.write(f"- {k}: {v}g")
                nutrients, effects = analyze_ingredients(ingr)
                st.write("영양소:")
                for k, v in nutrients.items():
                    st.write(f"- {k}: {v:.2f}")
                st.write("건강 효과:")
                for eff in effects:
                    st.write(f"✅ {eff}")
                st.write("맛 평가:")
                st.write(evaluate_flavor(ingr))
                if st.button(f"❌ 삭제", key=f"del_{fid}"):
                    delete_favorite(fid)
                    st.success("삭제 완료! 새로고침 해주세요.")