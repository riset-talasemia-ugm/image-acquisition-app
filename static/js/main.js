// Pendaftaran event dan inisialisasi. Dimuat paling akhir.
tabCapture.addEventListener("click", () => switchTab("capture"));
tabSegmentation.addEventListener("click", () => switchTab("segmentation"));
btnSegSelectImage.addEventListener("click", doSelectSegmentationImage);
btnLoadSegmentation.addEventListener("click", doLoadSegmentationResult);
btnRunSegmentation.addEventListener("click", doRunSegmentation);
btnSaveSegmentation.addEventListener("click", doSaveSegmentation);
btnSendToSegmentation.addEventListener("click", sendCaptureToSegmentation);
segTabSource.addEventListener("click", () => switchSegImageTab("source"));
segTabResult.addEventListener("click", () => switchSegImageTab("result"));
segClassTabTable.addEventListener("click", () => switchSegClassTab("table"));
segClassTabChart.addEventListener("click", () => switchSegClassTab("chart"));

btnSegAddCell.addEventListener("click", toggleSegAddMode);
btnSegCellShrink.addEventListener("click", () => resizeActiveCell(1 / 1.1));
btnSegCellGrow.addEventListener("click", () => resizeActiveCell(1.1));
segShowNumbersCheckbox.addEventListener("change", () => {
  segShowCellNumbers = segShowNumbersCheckbox.checked;
  renderSegmentationOverlay();
});
btnSegZoomIn.addEventListener("click", () => setSegZoom(segZoom + 0.25));
btnSegZoomOut.addEventListener("click", () => setSegZoom(segZoom - 0.25));
btnSegZoomReset.addEventListener("click", resetSegZoom);
segSourceBody.addEventListener("wheel", handleSegWheelZoom, { passive: false });
segResultBody.addEventListener("wheel", handleSegWheelZoom, { passive: false });
segSourceBody.addEventListener("mousedown", segMouseDown);
segResultBody.addEventListener("mousedown", segMouseDown);
window.addEventListener("mousemove", segMouseMove);
window.addEventListener("mouseup", segMouseUp);

btnSegPatientSummary.addEventListener("click", doLoadSegPatientSummary);
btnSegBatchRun.addEventListener("click", doSegBatchRun);
btnSegListResults.addEventListener("click", doLoadSegResultsListButton);
btnSegExportReport.addEventListener("click", doExportSegReport);
btnSegExportCoco.addEventListener("click", doExportSegDatasetCoco);
segResultsFilter.addEventListener("input", applySegResultsFilter);
segSelectAllCells.addEventListener("change", toggleSegSelectAll);
btnSegBulkApply.addEventListener("click", doSegBulkApply);
btnSegMarkRestCorrect.addEventListener("click", doSegMarkRestCorrect);
btnSegSaveModelConfig.addEventListener("click", doSaveSegModelConfig);

btnConnectCamera.addEventListener("click", connectCamera);
if (btnCameraSettings) btnCameraSettings.addEventListener("click", openCameraSettings);
btnRefreshCameras.addEventListener("click", loadCameras);
btnCapture.addEventListener("click", doCapture);
btnResetPeak.addEventListener("click", resetFocusPeak);
btnFolder.addEventListener("click", doSelectFolder);
btnSave.addEventListener("click", doSave);
btnSummary.addEventListener("click", loadFolderSummary);
btnCloseSummary.addEventListener("click", () => {
  summaryPanel.classList.add("summary-hidden");
  summaryDismissed = true;
});
patientNameInput.addEventListener("input", updateSaveButtonState);
autoToggle.addEventListener("change", () => setAutoMode(autoToggle.checked));

document.getElementById("btnTheme").addEventListener("click", toggleTheme);
document.getElementById("btnOpenSettings").addEventListener("click", () =>
  document.getElementById("settingsDialog").showModal()
);
document.getElementById("btnOpenReport").addEventListener("click", () =>
  document.getElementById("reportDialog").showModal()
);
document.querySelectorAll("dialog [data-close]").forEach((btn) =>
  btn.addEventListener("click", () => btn.closest("dialog").close())
);
segInspector.addEventListener("click", handleInspectorClick);

loadCameras().then(restoreCameraStatusIfConnected);
loadClassLegend();
loadSegModelStatus();
updateSaveButtonState();
renderInspector();
setInterval(checkCameraStatus, 2000);
setInterval(pollFocusLive, 700);
