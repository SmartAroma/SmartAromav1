"""Cabin sensing simulation and rule-based aroma recommendation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from smart_aroma.models.sequence_schema import (
    DURATION_LEVEL_CHOICES,
    PERSONA_CHOICES,
    SCENE_CHOICES,
)


class CabinContext(BaseModel):
    time_period: str = Field(..., description="早晨、白天、傍晚、夜间")
    drive_mode: str = Field(..., description="城市通勤、长途驾驶、停车休息")
    driver_state: str = Field(..., description="清醒、轻度疲劳、焦虑紧张、晕车不适")
    air_quality: str = Field(..., description="清新、一般、闷浊")
    temperature_c: int = Field(..., ge=10, le=38)
    humidity: int = Field(..., ge=20, le=90)
    co2_ppm: int = Field(..., ge=350, le=2500)

    @field_validator("time_period")
    @classmethod
    def validate_time_period(cls, value: str) -> str:
        choices = ("早晨", "白天", "傍晚", "夜间")
        if value not in choices:
            raise ValueError(f"time_period must be one of {choices}")
        return value

    @field_validator("drive_mode")
    @classmethod
    def validate_drive_mode(cls, value: str) -> str:
        choices = ("城市通勤", "长途驾驶", "停车休息")
        if value not in choices:
            raise ValueError(f"drive_mode must be one of {choices}")
        return value

    @field_validator("driver_state")
    @classmethod
    def validate_driver_state(cls, value: str) -> str:
        choices = ("清醒", "轻度疲劳", "焦虑紧张", "晕车不适")
        if value not in choices:
            raise ValueError(f"driver_state must be one of {choices}")
        return value

    @field_validator("air_quality")
    @classmethod
    def validate_air_quality(cls, value: str) -> str:
        choices = ("清新", "一般", "闷浊")
        if value not in choices:
            raise ValueError(f"air_quality must be one of {choices}")
        return value


class CabinRecommendation(BaseModel):
    scene: str
    persona: str
    duration_level: str
    confidence: int = Field(..., ge=0, le=100)
    cabin_score: int = Field(..., ge=0, le=100)
    alert_level: str
    summary: str
    reasons: list[str]
    environment_tags: list[str]

    @field_validator("scene")
    @classmethod
    def scene_must_be_known(cls, value: str) -> str:
        if value not in SCENE_CHOICES:
            raise ValueError(f"scene must be one of {SCENE_CHOICES}")
        return value

    @field_validator("persona")
    @classmethod
    def persona_must_be_known(cls, value: str) -> str:
        if value not in PERSONA_CHOICES:
            raise ValueError(f"persona must be one of {PERSONA_CHOICES}")
        return value

    @field_validator("duration_level")
    @classmethod
    def duration_must_be_known(cls, value: str) -> str:
        if value not in DURATION_LEVEL_CHOICES:
            raise ValueError(f"duration_level must be one of {DURATION_LEVEL_CHOICES}")
        return value


class CabinSnapshot(BaseModel):
    scenario_id: str
    scenario_name: str
    updated_at: str
    context: CabinContext
    recommendation: CabinRecommendation


SIMULATED_CABIN_SCENES: tuple[dict[str, object], ...] = (
    {
        "scenario_id": "morning_commute_fatigue",
        "scenario_name": "早高峰轻度疲劳通勤",
        "context": {
            "time_period": "早晨",
            "drive_mode": "城市通勤",
            "driver_state": "轻度疲劳",
            "air_quality": "一般",
            "temperature_c": 27,
            "humidity": 58,
            "co2_ppm": 980,
        },
    },
    {
        "scenario_id": "long_drive_stuffy",
        "scenario_name": "长途驾驶车内偏闷",
        "context": {
            "time_period": "白天",
            "drive_mode": "长途驾驶",
            "driver_state": "轻度疲劳",
            "air_quality": "闷浊",
            "temperature_c": 31,
            "humidity": 76,
            "co2_ppm": 1360,
        },
    },
    {
        "scenario_id": "parking_rest_anxious",
        "scenario_name": "停车休息情绪紧张",
        "context": {
            "time_period": "傍晚",
            "drive_mode": "停车休息",
            "driver_state": "焦虑紧张",
            "air_quality": "清新",
            "temperature_c": 24,
            "humidity": 52,
            "co2_ppm": 720,
        },
    },
    {
        "scenario_id": "night_clear_cruise",
        "scenario_name": "夜间稳定巡航",
        "context": {
            "time_period": "夜间",
            "drive_mode": "长途驾驶",
            "driver_state": "清醒",
            "air_quality": "清新",
            "temperature_c": 22,
            "humidity": 48,
            "co2_ppm": 680,
        },
    },
)


def simulated_cabin_snapshot(index: int | None = None) -> CabinSnapshot:
    now = datetime.now()
    scene_index = index if index is not None else (now.minute // 2) % len(SIMULATED_CABIN_SCENES)
    source = SIMULATED_CABIN_SCENES[scene_index % len(SIMULATED_CABIN_SCENES)]
    context_data = dict(source["context"])  # type: ignore[arg-type]

    drift = (now.second % 7) - 3
    context_data["temperature_c"] = int(context_data["temperature_c"]) + (drift // 3)
    context_data["humidity"] = max(20, min(90, int(context_data["humidity"]) + drift))
    context_data["co2_ppm"] = max(350, min(2500, int(context_data["co2_ppm"]) + drift * 12))

    context = CabinContext.model_validate(context_data)
    recommendation = recommend_from_cabin(context)
    return CabinSnapshot(
        scenario_id=str(source["scenario_id"]),
        scenario_name=str(source["scenario_name"]),
        updated_at=now.isoformat(timespec="seconds"),
        context=context,
        recommendation=recommendation,
    )


def recommend_from_cabin(context: CabinContext) -> CabinRecommendation:
    reasons: list[str] = []
    tags: list[str] = []
    score = 92
    scene = "通勤提神"
    persona = "专业调香师"
    duration = "标准"
    confidence = 82

    if context.driver_state == "轻度疲劳":
        scene = "通勤提神" if context.time_period != "早晨" else "晨间唤醒"
        duration = "速享"
        persona = "专业调香师"
        confidence += 8
        reasons.append("驾驶员出现轻度疲劳倾向，优先选择清爽提神但不过度刺激的方案。")
        tags.append("疲劳唤醒")
    elif context.driver_state == "焦虑紧张":
        scene = "静心冥想"
        duration = "标准"
        persona = "温柔恋人"
        confidence += 6
        reasons.append("驾驶员状态偏紧张，推荐更低刺激、更平稳的香气节奏。")
        tags.append("情绪缓和")
    elif context.driver_state == "晕车不适":
        scene = "通勤提神"
        duration = "速享"
        persona = "专业调香师"
        confidence += 4
        reasons.append("检测到晕车不适，控制为短时清爽方案，避免长时间浓香。")
        tags.append("低负担扩香")
    else:
        reasons.append("驾驶员状态清醒，系统按当前出行场景匹配舒适方案。")
        tags.append("稳定舒适")

    if context.drive_mode == "长途驾驶":
        if context.driver_state == "清醒":
            scene = "阅读专注"
        duration = "标准" if duration != "速享" else duration
        reasons.append("长途驾驶需要稳定注意力，香气节奏不宜频繁变化。")
        tags.append("长途稳定")
    elif context.drive_mode == "停车休息":
        scene = "静心冥想" if context.driver_state != "轻度疲劳" else scene
        persona = "温柔恋人"
        duration = "标准"
        reasons.append("当前为停车休息，允许使用更舒缓的陪伴型方案。")
        tags.append("停车休息")
    else:
        reasons.append("城市通勤节奏较短，推荐更快建立体感的方案。")
        tags.append("通勤场景")

    if context.time_period == "早晨" and context.driver_state != "焦虑紧张":
        scene = "晨间唤醒"
        reasons.append("早晨低唤醒状态更适合明亮、逐步拉起精神的香气。")
        tags.append("晨间唤醒")
    elif context.time_period == "夜间" and scene == "睡前安睡":
        scene = "静心冥想"
        reasons.append("夜间驾驶避免助眠倾向，改用沉静但不催眠的方案。")
        tags.append("夜间安全")

    if context.air_quality == "闷浊" or context.co2_ppm >= 1200:
        duration = "速享"
        score -= 18
        confidence += 5
        reasons.append("车内空气偏闷或 CO2 偏高，建议先通风，香薰控制为短时清新。")
        tags.append("建议通风")
    elif context.air_quality == "一般" or context.co2_ppm >= 900:
        score -= 8
        reasons.append("空气质量一般，采用中低负担扩香，避免让气味叠加沉闷感。")
        tags.append("空气一般")
    else:
        reasons.append("车内空气状态较好，可以进行正常强度的香气调节。")
        tags.append("空气清新")

    if context.temperature_c >= 30:
        score -= 8
        reasons.append("车内温度偏高，推荐更清爽的香型方向并避免沉重木质感。")
        tags.append("温度偏高")
    elif context.temperature_c <= 16:
        score -= 4
        reasons.append("车内温度偏低，香气可保持柔和稳定，减少冷感刺激。")
        tags.append("温度偏低")

    if context.humidity >= 75:
        score -= 6
        reasons.append("湿度偏高时气味扩散更容易显闷，系统降低方案时长负担。")
        duration = "速享" if duration == "标准" else duration
        tags.append("湿度偏高")
    elif context.humidity <= 30:
        score -= 4
        reasons.append("湿度偏低，推荐温和扩香，避免过强气流带来干燥感。")
        tags.append("湿度偏低")

    score = max(35, min(100, score))
    confidence = max(65, min(96, confidence))
    alert = "良好" if score >= 80 else "注意" if score >= 60 else "需通风"
    summary = f"{context.drive_mode} · {context.driver_state} · {context.air_quality}空气"

    return CabinRecommendation(
        scene=scene,
        persona=persona,
        duration_level=duration,
        confidence=confidence,
        cabin_score=score,
        alert_level=alert,
        summary=summary,
        reasons=reasons[:5],
        environment_tags=list(dict.fromkeys(tags))[:6],
    )
