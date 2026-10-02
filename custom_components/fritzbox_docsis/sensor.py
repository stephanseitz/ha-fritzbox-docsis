"""Sensors: power levels, signal quality, error counters and error rates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DocsisData, FritzDocsisConfigEntry, FritzDocsisCoordinator
from .entity import FritzDocsisEntity
from .parser import DownstreamChannel, UpstreamChannel

UNIT_DBMV = "dBmV"
UNIT_DB = "dB"

PARALLEL_UPDATES = 0

# State of "worst channel" when no channel has new correctable errors
NO_CHANNEL = "–"


# --------------------------------------------------------------------------- #
# Device-wide sensors
# --------------------------------------------------------------------------- #


def _ds_values(data: DocsisData, attr: str, docsis: str | None = None) -> list[float]:
    return [
        getattr(c, attr)
        for c in data.info.downstream.values()
        if getattr(c, attr) is not None and (docsis is None or c.docsis == docsis)
    ]


def _min(values: list[float]) -> float | None:
    return min(values) if values else None


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _ofdma_modulation(data: DocsisData) -> str | None:
    for ch in data.info.upstream.values():
        if ch.docsis == "3.1":
            return ch.modulation
    return None


def _worst_channel(data: DocsisData) -> str | None:
    rates = {k: v for k, v in data.corr_rate.items() if v is not None}
    if not rates:
        return None
    key = max(rates, key=lambda k: rates[k])
    if rates[key] <= 0:
        return NO_CHANNEL
    return data.info.downstream[key].label


def _worst_channel_attrs(data: DocsisData) -> dict[str, Any]:
    rates = sorted(
        ((k, v) for k, v in data.corr_rate.items() if v is not None),
        key=lambda kv: kv[1],
        reverse=True,
    )[:5]
    return {
        "top_channels": {data.info.downstream[k].label: v for k, v in rates},
    }


@dataclass(frozen=True, kw_only=True)
class DocsisSensorDescription(SensorEntityDescription):
    value_fn: Callable[[DocsisData], Any]
    attrs_fn: Callable[[DocsisData], dict[str, Any]] | None = None
    needs_log: bool = False


GLOBAL_SENSORS: tuple[DocsisSensorDescription, ...] = (
    DocsisSensorDescription(
        key="ds_power_min",
        native_unit_of_measurement=UNIT_DBMV,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: _min(_ds_values(d, "power_dbmv")),
    ),
    DocsisSensorDescription(
        key="ds_power_max",
        native_unit_of_measurement=UNIT_DBMV,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: _max(_ds_values(d, "power_dbmv")),
    ),
    DocsisSensorDescription(
        key="ds_mse_worst",
        native_unit_of_measurement=UNIT_DB,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        # MSE is negative: the highest (least negative) value is the worst one
        value_fn=lambda d: _max(_ds_values(d, "mse_db", "3.0")),
    ),
    DocsisSensorDescription(
        key="ds_mer_worst",
        native_unit_of_measurement=UNIT_DB,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: _min(_ds_values(d, "mer_db", "3.1")),
    ),
    DocsisSensorDescription(
        key="us_power_max",
        native_unit_of_measurement=UNIT_DBMV,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: _max(
            [c.power_dbmv for c in d.info.upstream.values() if c.power_dbmv is not None]
        ),
    ),
    DocsisSensorDescription(
        key="us_ofdma_modulation",
        icon="mdi:waveform",
        value_fn=_ofdma_modulation,
    ),
    DocsisSensorDescription(
        key="total_corr",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle-check-outline",
        value_fn=lambda d: d.total_corr,
    ),
    DocsisSensorDescription(
        key="total_noncorr",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle-outline",
        value_fn=lambda d: d.total_noncorr,
    ),
    DocsisSensorDescription(
        key="total_corr_rate",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:speedometer",
        value_fn=lambda d: d.total_corr_rate,
    ),
    DocsisSensorDescription(
        key="total_noncorr_rate",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:speedometer",
        value_fn=lambda d: d.total_noncorr_rate,
    ),
    DocsisSensorDescription(
        key="worst_channel",
        icon="mdi:sine-wave",
        value_fn=_worst_channel,
        attrs_fn=_worst_channel_attrs,
    ),
    DocsisSensorDescription(
        key="last_sync_lost",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:lan-disconnect",
        value_fn=lambda d: d.last_sync_lost,
        needs_log=True,
    ),
    DocsisSensorDescription(
        key="connected_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:lan-connect",
        value_fn=lambda d: d.connected_since,
        needs_log=True,
    ),
    DocsisSensorDescription(
        key="sync_losses_24h",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        value_fn=lambda d: d.sync_losses_24h,
        needs_log=True,
    ),
    DocsisSensorDescription(
        key="sync_losses_7d",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        value_fn=lambda d: d.sync_losses_7d,
        needs_log=True,
    ),
    DocsisSensorDescription(
        key="ds_channel_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.info.downstream),
    ),
    DocsisSensorDescription(
        key="us_channel_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.info.upstream),
    ),
)


class DocsisGlobalSensor(FritzDocsisEntity, SensorEntity):
    entity_description: DocsisSensorDescription

    def __init__(
        self, coordinator: FritzDocsisCoordinator, description: DocsisSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.needs_log:
            return self.coordinator.data.log_available
        return True

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


# --------------------------------------------------------------------------- #
# Per-channel sensors (created dynamically, keyed by frequency)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class ChannelMetric:
    key: str
    unit: str | None
    state_class: SensorStateClass
    value_fn: Callable[[DocsisData, str], Any]
    precision: int | None = None
    enabled_default: bool = True
    icon: str | None = None


def _ds(data: DocsisData, key: str) -> DownstreamChannel | None:
    return data.info.downstream.get(key)


def _us(data: DocsisData, key: str) -> UpstreamChannel | None:
    return data.info.upstream.get(key)


def _ds_attr(attr: str) -> Callable[[DocsisData, str], Any]:
    def fn(data: DocsisData, key: str) -> Any:
        ch = _ds(data, key)
        return None if ch is None else getattr(ch, attr)

    return fn


def _us_attr(attr: str) -> Callable[[DocsisData, str], Any]:
    def fn(data: DocsisData, key: str) -> Any:
        ch = _us(data, key)
        return None if ch is None else getattr(ch, attr)

    return fn


DS30_METRICS: tuple[ChannelMetric, ...] = (
    ChannelMetric(
        key="power",
        unit=UNIT_DBMV,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
        value_fn=_ds_attr("power_dbmv"),
    ),
    ChannelMetric(
        key="mse",
        unit=UNIT_DB,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
        value_fn=_ds_attr("mse_db"),
    ),
    ChannelMetric(
        key="corr",
        unit=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle-check-outline",
        value_fn=_ds_attr("corr_errors"),
    ),
    ChannelMetric(
        key="noncorr",
        unit=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle-outline",
        value_fn=_ds_attr("noncorr_errors"),
    ),
    ChannelMetric(
        key="corr_rate",
        unit=None,
        state_class=SensorStateClass.MEASUREMENT,
        precision=0,
        icon="mdi:speedometer",
        value_fn=lambda d, k: d.corr_rate.get(k),
    ),
    ChannelMetric(
        key="noncorr_rate",
        unit=None,
        state_class=SensorStateClass.MEASUREMENT,
        precision=0,
        icon="mdi:speedometer",
        enabled_default=False,
        value_fn=lambda d, k: d.noncorr_rate.get(k),
    ),
)

DS31_METRICS: tuple[ChannelMetric, ...] = (
    ChannelMetric(
        key="power",
        unit=UNIT_DBMV,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
        value_fn=_ds_attr("power_dbmv"),
    ),
    ChannelMetric(
        key="mer",
        unit=UNIT_DB,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
        value_fn=_ds_attr("mer_db"),
    ),
    ChannelMetric(
        key="noncorr",
        unit=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle-outline",
        value_fn=_ds_attr("noncorr_errors"),
    ),
    ChannelMetric(
        key="noncorr_rate",
        unit=None,
        state_class=SensorStateClass.MEASUREMENT,
        precision=0,
        icon="mdi:speedometer",
        value_fn=lambda d, k: d.noncorr_rate.get(k),
    ),
)

US_METRICS: tuple[ChannelMetric, ...] = (
    ChannelMetric(
        key="power",
        unit=UNIT_DBMV,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
        value_fn=_us_attr("power_dbmv"),
    ),
)


def _prefix(channel: DownstreamChannel | UpstreamChannel, direction: str) -> str:
    if channel.docsis == "3.1":
        return f"{direction} {'OFDM' if direction == 'DS' else 'OFDMA'} {channel.label}"
    return f"{direction} {channel.label}"


class DocsisChannelSensor(FritzDocsisEntity, SensorEntity):
    """One metric of a single channel."""

    def __init__(
        self,
        coordinator: FritzDocsisCoordinator,
        channel_key: str,
        title: str,
        metric: ChannelMetric,
        is_upstream: bool,
    ) -> None:
        super().__init__(coordinator, f"{channel_key}_{metric.key}")
        self._channel_key = channel_key
        self._metric = metric
        self._is_upstream = is_upstream
        self._attr_translation_key = f"channel_{metric.key}"
        self._attr_translation_placeholders = {"channel": title}
        self._attr_native_unit_of_measurement = metric.unit
        self._attr_state_class = metric.state_class
        self._attr_suggested_display_precision = metric.precision
        self._attr_entity_registry_enabled_default = metric.enabled_default
        if metric.icon:
            self._attr_icon = metric.icon

    def _channel(self) -> DownstreamChannel | UpstreamChannel | None:
        data = self.coordinator.data
        source = data.info.upstream if self._is_upstream else data.info.downstream
        return source.get(self._channel_key)

    @property
    def available(self) -> bool:
        return super().available and self._channel() is not None

    @property
    def native_value(self) -> Any:
        return self._metric.value_fn(self.coordinator.data, self._channel_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        ch = self._channel()
        if ch is None:
            return None
        attrs: dict[str, Any] = {
            "docsis": ch.docsis,
            "channel_id": ch.channel_id,
            "frequency_mhz": ch.frequency_mhz,
            "modulation": ch.modulation,
        }
        if ch.frequency_end_mhz is not None:
            attrs["frequency_end_mhz"] = ch.frequency_end_mhz
        if isinstance(ch, UpstreamChannel) and ch.active_subcarriers is not None:
            attrs["active_subcarriers"] = ch.active_subcarriers
        return attrs


# --------------------------------------------------------------------------- #


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzDocsisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(DocsisGlobalSensor(coordinator, d) for d in GLOBAL_SENSORS)

    known: set[str] = set()

    @callback
    def _add_channel_entities() -> None:
        data = coordinator.data
        if data is None:
            return
        new: list[SensorEntity] = []
        for key, ch in data.info.downstream.items():
            if key in known:
                continue
            known.add(key)
            metrics = DS30_METRICS if ch.docsis == "3.0" else DS31_METRICS
            title = _prefix(ch, "DS")
            new.extend(
                DocsisChannelSensor(coordinator, key, title, m, False) for m in metrics
            )
        for key, ch in data.info.upstream.items():
            if key in known:
                continue
            known.add(key)
            title = _prefix(ch, "US")
            new.extend(
                DocsisChannelSensor(coordinator, key, title, m, True)
                for m in US_METRICS
            )
        if new:
            async_add_entities(new)

    _add_channel_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_channel_entities))
