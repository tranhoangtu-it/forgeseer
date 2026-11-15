// Lịch cống các ngày tới - nối SAU live_capture.js thành một script Frida, dùng lại helper của
// file đó: invoke, toJson, readManagedString, fakeCampaign, quotaOf, quotaMethod, CAMPAIGN_OFF,
// QUOTA_TOLERANCE.
//
// ForgeCampaign.$Gf() gọi trên campaign GIẢ LẬP (JsonUtility.FromJson) với round = ngày cần tính.
// Ngày mai: tributeCredit = nextTributeCredit (giảm do nộp dư hôm nay). Các ngày sau: credit = 0
// vì phần nộp dư tương lai chưa biết (=> số liệu là mức trần). Tự kiểm: campaign giả lập của hôm
// nay phải cho đúng `quota` của phòng rèn, lệch -> không gửi gì (mảng rỗng).

const SCHEDULE_MAX_DAYS = 10;
let lastScheduleKey = '';
let lastSchedule = [];

function forecastSchedule(roomObj, quota) {
  if (quotaMethod.isNull()) return [];
  const campaignObj = roomObj.add(CAMPAIGN_OFF).readPointer();
  const campaign = JSON.parse(readManagedString(invoke(toJson, NULL, [campaignObj])));
  const key = JSON.stringify([campaign.round, campaign.tributeCredit, campaign.nextTributeCredit,
                              campaign.contractDeadlineRound, campaign.relics, quota]);
  if (key === lastScheduleKey) return lastSchedule;
  lastScheduleKey = key;
  lastSchedule = [];
  const today = quotaOf(fakeCampaign(campaign, {}));
  if (Math.abs(today - quota) > QUOTA_TOLERANCE) return lastSchedule;
  const deadline = campaign.contractDeadlineRound || campaign.round + 1;
  const last = Math.min(deadline, campaign.round + SCHEDULE_MAX_DAYS);
  for (let day = campaign.round + 1; day <= last; day++) {
    const credit = day === campaign.round + 1 ? (campaign.nextTributeCredit || 0) : 0;
    lastSchedule.push(quotaOf(fakeCampaign(campaign, {
      round: day, tributeCredit: credit, nextTributeCredit: 0 })));
  }
  return lastSchedule;
}
