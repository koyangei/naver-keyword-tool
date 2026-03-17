import streamlit as st
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import platform
import os

# 네이버 API 키 입력
client_id = st.secrets["NAVER_CLIENT_ID"]
client_secret = st.secrets["NAVER_CLIENT_SECRET"]

st.set_page_config(page_title="네이버 키워드 트렌드 분석 툴", layout="wide")

# 한글 폰트 설정
def set_korean_font():
    if platform.system() == "Windows":
        plt.rcParams["font.family"] = "Malgun Gothic"
    elif platform.system() == "Darwin":
        plt.rcParams["font.family"] = "AppleGothic"
    else:
        font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
        if os.path.exists(font_path):
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams["font.family"] = font_prop.get_name()

    plt.rcParams["axes.unicode_minus"] = False

set_korean_font()

# 카드형 대시보드용 CSS
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.dashboard-card {
    background-color: #ffffff;
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #e9ecef;
    box-shadow: 0px 2px 8px rgba(0,0,0,0.04);
    min-height: 120px;
}

.card-title {
    font-size: 14px;
    color: #6c757d;
    margin-bottom: 10px;
}

.card-value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.3;
    color: #212529;
    word-break: keep-all;
}

.card-sub {
    font-size: 13px;
    color: #868e96;
    margin-top: 8px;
}

.insight-card {
    background-color: #fafafa;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #eeeeee;
    min-height: 150px;
    line-height: 1.7;
}

.insight-title {
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 10px;
    color: #212529;
}

.section-gap {
    margin-top: 22px;
}

div[data-testid="stDataFrame"] {
    border: 1px solid #edf0f2;
    border-radius: 12px;
    padding: 4px;
}
</style>
""", unsafe_allow_html=True)

st.title("네이버 키워드 트렌드 분석 대시보드")
st.caption("전체 / PC / 모바일 기준 키워드 검색 트렌드를 비교하고 인사이트를 확인합니다.")

def format_period_label(period_text, time_unit="month"):
    dt = pd.to_datetime(period_text)

    if time_unit == "date":
        return f"{dt.year}년 {dt.month}월 {dt.day}일"
    elif time_unit == "week":
        week_of_month = ((dt.day - 1) // 7) + 1
        return f"{dt.year}년 {dt.month}월 {week_of_month}주차"
    else:
        return f"{dt.year}년 {dt.month}월"

def make_chart_period_label(series, time_unit="month"):
    dt = pd.to_datetime(series)

    if time_unit == "date":
        return dt.dt.strftime("%m-%d")
    elif time_unit == "week":
        return dt.apply(lambda x: f"{x.month}월 {((x.day - 1) // 7) + 1}주")
    else:
        return dt.dt.strftime("%Y-%m")

@st.cache_data(show_spinner=False)
def call_naver_datalab(keyword_list, start_date, end_date, time_unit="month", device=None):
    url = "https://openapi.naver.com/v1/datalab/search"

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json"
    }

    keyword_groups = []
    for k in keyword_list:
        keyword_groups.append({
            "groupName": k,
            "keywords": [k]
        })

    body = {
        "startDate": str(start_date),
        "endDate": str(end_date),
        "timeUnit": time_unit,
        "keywordGroups": keyword_groups
    }

    if device:
        body["device"] = device

    response = requests.post(url, headers=headers, data=json.dumps(body))

    if response.status_code != 200:
        st.error(f"API 호출 실패: {response.status_code}")
        st.text(response.text)
        st.stop()

    data = response.json()

    if "results" not in data:
        st.error("응답 데이터 형식이 올바르지 않습니다.")
        st.write(data)
        st.stop()

    df_list = []
    for r in data["results"]:
        temp = pd.DataFrame(r["data"])
        temp["keyword"] = r["title"]
        df_list.append(temp)

    if not df_list:
        return pd.DataFrame()

    df = pd.concat(df_list, ignore_index=True)
    df["ratio"] = pd.to_numeric(df["ratio"], errors="coerce")
    df = df.dropna(subset=["ratio"])
    return df

def make_summary_df(df, time_unit="month"):
    if df.empty:
        return pd.DataFrame()

    summary_rows = []

    for keyword in df["keyword"].unique():
        subset = df[df["keyword"] == keyword].copy().sort_values("period").reset_index(drop=True)

        start_period = subset.iloc[0]["period"]
        start_ratio = subset.iloc[0]["ratio"]

        end_period = subset.iloc[-1]["period"]
        end_ratio = subset.iloc[-1]["ratio"]

        max_idx = subset["ratio"].idxmax()
        min_idx = subset["ratio"].idxmin()

        max_row = subset.loc[max_idx]
        min_row = subset.loc[min_idx]

        max_period = max_row["period"]
        max_ratio = max_row["ratio"]

        min_period = min_row["period"]
        min_ratio = min_row["ratio"]

        avg_ratio = subset["ratio"].mean()
        total_ratio = subset["ratio"].sum()
        change = end_ratio - start_ratio

        if start_ratio == 0:
            change_rate = 0
        else:
            change_rate = ((end_ratio - start_ratio) / start_ratio) * 100

        summary_rows.append({
            "keyword": keyword,
            "시작 기간": format_period_label(start_period, time_unit),
            "시작 관심도": round(start_ratio, 2),
            "최종 기간": format_period_label(end_period, time_unit),
            "최종 관심도": round(end_ratio, 2),
            "평균 관심도": round(avg_ratio, 2),
            "누적 관심도": round(total_ratio, 2),
            "최고 관심도 발생 기간": format_period_label(max_period, time_unit),
            "최고 관심도": round(max_ratio, 2),
            "최저 관심도 발생 기간": format_period_label(min_period, time_unit),
            "최저 관심도": round(min_ratio, 2),
            "증감": round(change, 2),
            "증감률(%)": round(change_rate, 2)
        })

    summary_df = pd.DataFrame(summary_rows)
    return summary_df.sort_values("증감률(%)", ascending=False).reset_index(drop=True)

def draw_line_chart(df, title, time_unit="month"):
    st.subheader(title)

    if df.empty:
        st.info("조회 결과가 없습니다.")
        return

    fig, ax = plt.subplots(figsize=(12, 5))

    for keyword in df["keyword"].unique():
        subset = df[df["keyword"] == keyword].sort_values("period").copy()
        subset["period_label"] = make_chart_period_label(subset["period"], time_unit)
        ax.plot(subset["period_label"], subset["ratio"], marker="o", label=keyword)

    ax.set_xlabel("기간")
    ax.set_ylabel("검색 관심도")
    ax.legend(title="키워드", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

def render_summary_metrics(summary_df, label):
    if summary_df.empty:
        st.info(f"{label} 데이터가 없습니다.")
        return None, None, None

    top_keyword = summary_df.sort_values("최고 관심도", ascending=False).iloc[0]

    rising_df = summary_df[summary_df["증감률(%)"] > 0].sort_values("증감률(%)", ascending=False)
    falling_df = summary_df[summary_df["증감률(%)"] < 0].sort_values("증감률(%)", ascending=True)

    top_rising = rising_df.iloc[0] if not rising_df.empty else None
    top_falling = falling_df.iloc[0] if not falling_df.empty else None

    total_interest_sum = round(summary_df["누적 관심도"].sum(), 2)

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">{label} 분석 키워드 수</div>
            <div class="card-value">{len(summary_df)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">{label} 기간 내 관심도 총합</div>
            <div class="card-value">{total_interest_sum:,.1f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">{label} 최고 관심도 키워드</div>
            <div class="card-value">{top_keyword["keyword"]}</div>
            <div class="card-sub">{top_keyword["최고 관심도 발생 기간"]}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        if top_rising is not None:
            st.markdown(f"""
            <div class="dashboard-card">
                <div class="card-title">{label} 최고 상승 키워드</div>
                <div class="card-value">{top_rising["keyword"]}</div>
                <div class="card-sub">+{top_rising["증감률(%)"]:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="dashboard-card">
                <div class="card-title">{label} 최고 상승 키워드</div>
                <div class="card-value">없음</div>
                <div class="card-sub">상승 키워드 미확인</div>
            </div>
            """, unsafe_allow_html=True)

    with col5:
        if top_falling is not None:
            st.markdown(f"""
            <div class="dashboard-card">
                <div class="card-title">{label} 최고 하락 키워드</div>
                <div class="card-value">{top_falling["keyword"]}</div>
                <div class="card-sub">{top_falling["증감률(%)"]:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="dashboard-card">
                <div class="card-title">{label} 최고 하락 키워드</div>
                <div class="card-value">없음</div>
                <div class="card-sub">하락 키워드 미확인</div>
            </div>
            """, unsafe_allow_html=True)

    return top_keyword, top_rising, top_falling

def render_insight_cards(summary_df, label):
    if summary_df.empty:
        return

    top_keyword = summary_df.sort_values("최고 관심도", ascending=False).iloc[0]

    rising_df = summary_df[summary_df["증감률(%)"] > 0].sort_values("증감률(%)", ascending=False)
    falling_df = summary_df[summary_df["증감률(%)"] < 0].sort_values("증감률(%)", ascending=True)

    top_rising = rising_df.iloc[0] if not rising_df.empty else None
    top_falling = falling_df.iloc[0] if not falling_df.empty else None

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="insight-card">
            <div class="insight-title">핵심 키워드</div>
            <div>
                <b>{top_keyword["keyword"]}</b> 키워드는 {label} 기준
                <b>{top_keyword["최고 관심도 발생 기간"]}</b>에 최고 관심도를 기록했습니다.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        if top_rising is not None:
            st.markdown(f"""
            <div class="insight-card">
                <div class="insight-title">상승 키워드</div>
                <div>
                    <b>{top_rising["keyword"]}</b> 키워드는
                    <b>{top_rising["시작 기간"]}</b> 대비
                    <b>{top_rising["최종 기간"]}</b> 기준
                    상승 흐름이 확인됩니다.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="insight-card">
                <div class="insight-title">상승 키워드</div>
                <div>뚜렷한 상승 흐름이 확인된 키워드가 없습니다.</div>
            </div>
            """, unsafe_allow_html=True)

    with col3:
        if top_falling is not None:
            st.markdown(f"""
            <div class="insight-card">
                <div class="insight-title">하락 키워드</div>
                <div>
                    <b>{top_falling["keyword"]}</b> 키워드는
                    <b>{top_falling["시작 기간"]}</b> 대비
                    <b>{top_falling["최종 기간"]}</b> 기준
                    하락 흐름이 나타났습니다.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="insight-card">
                <div class="insight-title">하락 키워드</div>
                <div>뚜렷한 하락 흐름이 확인된 키워드가 없습니다.</div>
            </div>
            """, unsafe_allow_html=True)

def render_device_share(summary_pc, summary_mobile):
    if summary_pc.empty or summary_mobile.empty:
        st.info("디바이스 점유율을 계산할 데이터가 없습니다.")
        return

    pc_total = float(summary_pc["누적 관심도"].sum())
    mobile_total = float(summary_mobile["누적 관심도"].sum())
    total = pc_total + mobile_total

    if total == 0:
        pc_share = 0
        mobile_share = 0
    else:
        pc_share = (pc_total / total) * 100
        mobile_share = (mobile_total / total) * 100

    st.subheader("디바이스 점유율")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">PC 기간 내 관심도 총합</div>
            <div class="card-value">{pc_total:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">모바일 기간 내 관심도 총합</div>
            <div class="card-value">{mobile_total:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">PC 비중</div>
            <div class="card-value">{pc_share:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">모바일 비중</div>
            <div class="card-value">{mobile_share:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

def render_keyword_power(summary_df, label_kr):
    if summary_df.empty:
        st.info(f"{label_kr} 영향력 순위를 계산할 데이터가 없습니다.")
        return

    power_df = summary_df[["keyword", "누적 관심도", "최고 관심도", "증감률(%)"]].copy()
    power_df = power_df.sort_values("누적 관심도", ascending=False).reset_index(drop=True)
    power_df.index = power_df.index + 1
    power_df["순위"] = power_df.index

    st.markdown(f"#### {label_kr} 키워드 영향력 순위")
    st.dataframe(
        power_df[["순위", "keyword", "누적 관심도", "최고 관심도", "증감률(%)"]],
        use_container_width=True
    )

def render_keyword_flow_cards(summary_df, label_kr):
    if summary_df.empty:
        st.info(f"{label_kr} 키워드 흐름 분류를 계산할 데이터가 없습니다.")
        return

    rising_keywords = summary_df[summary_df["증감률(%)"] > 5]["keyword"].tolist()
    stable_keywords = summary_df[
        (summary_df["증감률(%)"] >= -5) & (summary_df["증감률(%)"] <= 5)
    ]["keyword"].tolist()
    falling_keywords = summary_df[summary_df["증감률(%)"] < -5]["keyword"].tolist()

    def join_keywords(keyword_list):
        return ", ".join(keyword_list) if keyword_list else "해당 없음"

    st.subheader(f"{label_kr} 키워드 흐름 분류")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">상승 키워드</div>
            <div class="card-value" style="font-size:18px;">{join_keywords(rising_keywords)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">안정 키워드</div>
            <div class="card-value" style="font-size:18px;">{join_keywords(stable_keywords)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">하락 키워드</div>
            <div class="card-value" style="font-size:18px;">{join_keywords(falling_keywords)}</div>
        </div>
        """, unsafe_allow_html=True)

def classify_rising_status(prev_growth, avg_growth):
    if prev_growth >= 40 and avg_growth >= 50:
        return "강한 급등"
    elif prev_growth >= 20 and avg_growth >= 30:
        return "급등"
    else:
        return "관찰 필요"

def find_rising_start_point(df, keyword, min_prev_growth=5):
    temp = df[df["keyword"] == keyword].copy().sort_values("period").reset_index(drop=True)

    if len(temp) < 2:
        return None

    for i in range(1, len(temp)):
        before = float(temp.iloc[i - 1]["ratio"])
        after = float(temp.iloc[i]["ratio"])

        if before > 0:
            growth = ((after - before) / before) * 100
            if growth >= min_prev_growth:
                return {
                    "period": temp.iloc[i]["period"],
                    "ratio": temp.iloc[i]["ratio"]
                }

    return None

def detect_rising_keywords(df, time_unit="month", min_current=20, min_prev_growth=20, min_avg_growth=30):
    if df.empty:
        return pd.DataFrame()

    results = []

    for keyword in df["keyword"].unique():
        temp = df[df["keyword"] == keyword].copy().sort_values("period").reset_index(drop=True)

        if len(temp) < 4:
            continue

        current = float(temp.iloc[-1]["ratio"])
        previous = float(temp.iloc[-2]["ratio"])
        recent_avg = float(temp.iloc[-4:-1]["ratio"].mean())

        if previous <= 0 or recent_avg <= 0:
            continue

        prev_growth = ((current - previous) / previous) * 100
        avg_growth = ((current - recent_avg) / recent_avg) * 100

        recent_window = temp.iloc[-4:].copy()
        start_idx = None

        for i in range(1, len(recent_window)):
            before = float(recent_window.iloc[i - 1]["ratio"])
            after = float(recent_window.iloc[i]["ratio"])

            if before > 0:
                growth = ((after - before) / before) * 100
                if growth >= min_prev_growth:
                    start_idx = recent_window.index[i]
                    break

        if start_idx is None:
            surge_start_period = temp.iloc[-1]["period"]
        else:
            surge_start_period = temp.loc[start_idx, "period"]

        # 초기 급등 시점 찾기
        initial_point = find_rising_start_point(df, keyword, min_prev_growth)

        if initial_point is not None:
            initial_period = initial_point["period"]
        else:
            initial_period = surge_start_period

        if (
            current >= min_current
            and prev_growth >= min_prev_growth
            and avg_growth >= min_avg_growth
        ):
            results.append({
                "키워드": keyword,
                "현재 관심도": round(current, 2),
                "직전 구간 관심도": round(previous, 2),
                "최근 3구간 평균 관심도": round(recent_avg, 2),
                "직전 대비 상승률(%)": round(prev_growth, 2),
                "최근 평균 대비 상승률(%)": round(avg_growth, 2),
                "급등 시작 시점(초기)": format_period_label(initial_period, time_unit),
                "급등 확정 시점": format_period_label(surge_start_period, time_unit),
                "상태": classify_rising_status(prev_growth, avg_growth),
                "활용 제안": "광고 확대 검토" if avg_growth >= 50 else "모니터링 추천"
            })

    result_df = pd.DataFrame(results)

    if not result_df.empty:
        result_df = result_df.sort_values(
            ["최근 평균 대비 상승률(%)", "직전 대비 상승률(%)"],
            ascending=False
        ).reset_index(drop=True)

    return result_df

def render_rising_summary_cards(rising_df):
    if rising_df.empty:
        st.info("조건에 해당하는 급등 키워드가 없습니다.")
        return

    top_keyword = rising_df.iloc[0]
    strong_count = len(rising_df[rising_df["상태"] == "강한 급등"])
    monitor_count = len(rising_df[rising_df["활용 제안"] == "모니터링 추천"])

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">급등 키워드 수</div>
            <div class="card-value">{len(rising_df)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">최고 급등 키워드</div>
            <div class="card-value">{top_keyword["키워드"]}</div>
            <div class="card-sub">최근 평균 대비 {top_keyword["최근 평균 대비 상승률(%)"]:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">강한 급등 키워드</div>
            <div class="card-value">{strong_count}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="dashboard-card">
            <div class="card-title">모니터링 추천 키워드</div>
            <div class="card-value">{monitor_count}</div>
        </div>
        """, unsafe_allow_html=True)

def render_rising_insight(rising_df):
    if rising_df.empty:
        return

    top_keyword = rising_df.iloc[0]
    st.markdown("### 급등 키워드 인사이트")
    st.write(
        f"- **{top_keyword['키워드']}** 키워드는 최근 평균 대비 "
        f"**{top_keyword['최근 평균 대비 상승률(%)']}%** 상승하며 가장 강한 급등 흐름을 보였습니다."
    )
    st.write(
        f"- 초기 급등 시점은 **{top_keyword['급등 시작 시점(초기)']}**, "
        f"급등 확정 시점은 **{top_keyword['급등 확정 시점']}** 으로 해석할 수 있으며, "
        f"현재 관심도는 **{top_keyword['현재 관심도']}** 입니다."
    )

    strong_keywords = rising_df[rising_df["상태"] == "강한 급등"]["키워드"].tolist()
    if strong_keywords:
        st.write(f"- **강한 급등** 상태 키워드: {', '.join(strong_keywords)}")

    ad_keywords = rising_df[rising_df["활용 제안"] == "광고 확대 검토"]["키워드"].tolist()
    if ad_keywords:
        st.write(f"- 광고 운영 관점에서 **확대 검토 후보**: {', '.join(ad_keywords)}")

def draw_rising_keyword_chart(df, keyword, title, time_unit="month", min_prev_growth=5):
    chart_df = df[df["keyword"] == keyword].copy().sort_values("period")

    if chart_df.empty:
        st.info("그래프를 그릴 데이터가 없습니다.")
        return

    chart_df["period_label"] = make_chart_period_label(chart_df["period"], time_unit)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(chart_df["period_label"], chart_df["ratio"], marker="o", label=keyword)

    # 마지막 시점 표시
    ax.scatter(
        chart_df["period_label"].iloc[-1],
        chart_df["ratio"].iloc[-1],
        s=120,
        label="현재 시점"
    )

    # 급등 시작 시점 찾기
    rising_point = find_rising_start_point(df, keyword, min_prev_growth=min_prev_growth)

    if rising_point is not None:
        rising_period_label = make_chart_period_label(
            pd.Series([rising_point["period"]]),
            time_unit
        ).iloc[0]

        ax.scatter(
            rising_period_label,
            rising_point["ratio"],
            s=180,
            marker="o",
            color="red",
            label="급등 시작 시점"
        )

        ax.annotate(
            "급등 시작",
            (rising_period_label, rising_point["ratio"]),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center"
        )

        st.caption(
            f"급등 시작 시점: {format_period_label(rising_point['period'], time_unit)} / "
            f"관심도: {round(rising_point['ratio'], 2)}"
        )

    ax.set_title(title)
    ax.set_xlabel("기간")
    ax.set_ylabel("검색 관심도")
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

# 세션 상태 초기화
if "analysis_run" not in st.session_state:
    st.session_state.analysis_run = False
if "df_all" not in st.session_state:
    st.session_state.df_all = None
if "df_pc" not in st.session_state:
    st.session_state.df_pc = None
if "df_mobile" not in st.session_state:
    st.session_state.df_mobile = None
if "summary_all" not in st.session_state:
    st.session_state.summary_all = None
if "summary_pc" not in st.session_state:
    st.session_state.summary_pc = None
if "summary_mobile" not in st.session_state:
    st.session_state.summary_mobile = None
if "last_params" not in st.session_state:
    st.session_state.last_params = None

# 입력 영역
st.markdown("### 분석 조건")
keywords = st.text_input("키워드 입력 (쉼표로 구분)", "꽃배달, 개업화분, 근조화환")

col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input("시작 날짜")
with col2:
    end_date = st.date_input("종료 날짜")
with col3:
    time_unit = st.selectbox("분석 단위", ["date", "week", "month"], index=2)

if st.button("트렌드 분석"):
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    if not keyword_list:
        st.warning("키워드를 1개 이상 입력해주세요.")
        st.stop()

    if start_date > end_date:
        st.warning("시작 날짜가 종료 날짜보다 늦을 수 없습니다.")
        st.stop()

    st.session_state.analysis_run = True
    st.session_state.last_params = {
        "keywords": keyword_list,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "time_unit": time_unit,
    }

    df_all = call_naver_datalab(tuple(keyword_list), str(start_date), str(end_date), time_unit=time_unit, device=None)
    df_pc = call_naver_datalab(tuple(keyword_list), str(start_date), str(end_date), time_unit=time_unit, device="pc")
    df_mobile = call_naver_datalab(tuple(keyword_list), str(start_date), str(end_date), time_unit=time_unit, device="mo")

    summary_all = make_summary_df(df_all, time_unit)
    summary_pc = make_summary_df(df_pc, time_unit)
    summary_mobile = make_summary_df(df_mobile, time_unit)

    st.session_state.df_all = df_all
    st.session_state.df_pc = df_pc
    st.session_state.df_mobile = df_mobile
    st.session_state.summary_all = summary_all
    st.session_state.summary_pc = summary_pc
    st.session_state.summary_mobile = summary_mobile

if st.session_state.analysis_run:
    df_all = st.session_state.df_all
    df_pc = st.session_state.df_pc
    df_mobile = st.session_state.df_mobile
    summary_all = st.session_state.summary_all
    summary_pc = st.session_state.summary_pc
    summary_mobile = st.session_state.summary_mobile
    saved_time_unit = st.session_state.last_params["time_unit"]

    main_tab1, main_tab2 = st.tabs(["트렌드 분석", "급등 키워드 탐지"])

    with main_tab1:
        st.subheader("핵심 요약")
        tab1, tab2, tab3 = st.tabs(["전체", "PC", "모바일"])

        with tab1:
            render_summary_metrics(summary_all, "전체")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 키워드 인사이트")
            render_insight_cards(summary_all, "전체")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 트렌드 분석")
            left, right = st.columns([2, 1])

            with left:
                draw_line_chart(df_all, "전체 트렌드 그래프", saved_time_unit)

            with right:
                render_keyword_power(summary_all, "전체")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            render_keyword_flow_cards(summary_all, "전체")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 전체 요약표")
            st.dataframe(summary_all, use_container_width=True)

        with tab2:
            render_summary_metrics(summary_pc, "PC")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 키워드 인사이트")
            render_insight_cards(summary_pc, "PC")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 트렌드 분석")
            left, right = st.columns([2, 1])

            with left:
                draw_line_chart(df_pc, "PC 트렌드 그래프", saved_time_unit)

            with right:
                render_keyword_power(summary_pc, "PC")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            render_keyword_flow_cards(summary_pc, "PC")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### PC 요약표")
            st.dataframe(summary_pc, use_container_width=True)

        with tab3:
            render_summary_metrics(summary_mobile, "모바일")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 키워드 인사이트")
            render_insight_cards(summary_mobile, "모바일")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 트렌드 분석")
            left, right = st.columns([2, 1])

            with left:
                draw_line_chart(df_mobile, "모바일 트렌드 그래프", saved_time_unit)

            with right:
                render_keyword_power(summary_mobile, "모바일")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            render_keyword_flow_cards(summary_mobile, "모바일")

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 모바일 요약표")
            st.dataframe(summary_mobile, use_container_width=True)

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        render_device_share(summary_pc, summary_mobile)

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        st.subheader("PC / 모바일 비교표")

        compare_df = pd.merge(
            summary_pc[["keyword", "최종 관심도", "증감률(%)", "누적 관심도"]].rename(columns={
                "최종 관심도": "PC 최종 관심도",
                "증감률(%)": "PC 증감률(%)",
                "누적 관심도": "PC 기간 내 관심도 총합"
            }),
            summary_mobile[["keyword", "최종 관심도", "증감률(%)", "누적 관심도"]].rename(columns={
                "최종 관심도": "모바일 최종 관심도",
                "증감률(%)": "모바일 증감률(%)",
                "누적 관심도": "모바일 기간 내 관심도 총합"
            }),
            on="keyword",
            how="outer"
        )

        st.dataframe(compare_df, use_container_width=True)

        csv_compare = compare_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="PC/모바일 비교표 CSV 다운로드",
            data=csv_compare,
            file_name="naver_keyword_device_compare.csv",
            mime="text/csv"
        )

        with st.expander("원본 데이터 보기"):
            st.markdown("#### 전체")
            st.dataframe(df_all, use_container_width=True)
            st.markdown("#### PC")
            st.dataframe(df_pc, use_container_width=True)
            st.markdown("#### 모바일")
            st.dataframe(df_mobile, use_container_width=True)

    with main_tab2:
        st.subheader("급등 키워드 탐지")
        st.caption("최근 구간 기준으로 급등한 키워드를 자동 탐지합니다. 현재는 전체 트렌드 데이터를 기준으로 탐지합니다.")

        c1, c2, c3 = st.columns(3)

        with c1:
            min_current = st.number_input(
                "최소 현재 관심도",
                min_value=0,
                value=5,
                step=1
            )

        with c2:
            min_prev_growth = st.number_input(
                "직전 대비 최소 상승률(%)",
                min_value=0,
                value=5,
                step=5
            )

        with c3:
            min_avg_growth = st.number_input(
                "최근 평균 대비 최소 상승률(%)",
                min_value=0,
                value=5,
                step=5
            )

        rising_df = detect_rising_keywords(
            df_all,
            time_unit=saved_time_unit,
            min_current=min_current,
            min_prev_growth=min_prev_growth,
            min_avg_growth=min_avg_growth
        )

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        render_rising_summary_cards(rising_df)

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        render_rising_insight(rising_df)

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        st.markdown("### 급등 키워드 결과표")

        if rising_df.empty:
            st.info("현재 조건에 해당하는 급등 키워드가 없습니다. 조건을 완화해서 다시 확인해보세요.")
        else:
            st.dataframe(rising_df, use_container_width=True)

            csv_rising = rising_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="급등 키워드 결과 CSV 다운로드",
                data=csv_rising,
                file_name="naver_rising_keywords.csv",
                mime="text/csv"
            )

            st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
            st.markdown("### 급등 키워드 추이 그래프")

            selected_keyword = st.selectbox(
                "그래프로 확인할 급등 키워드 선택",
                rising_df["키워드"].tolist()
            )

            draw_rising_keyword_chart(
                df_all,
                selected_keyword,
                f"{selected_keyword} 급등 추이 그래프",
                saved_time_unit,
                min_prev_growth=min_prev_growth
            )