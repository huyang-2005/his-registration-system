-- ============================================================
-- 门诊挂号分系统 - 测试用模拟数据
-- 说明：排班日期使用本地当天/次日，保证演示时可直接挂号
-- ============================================================

PRAGMA foreign_keys = ON;

-- ---------------------- 系统用户 ----------------------
INSERT INTO sys_user (username, password, real_name, role) VALUES
('guahao',  '123456', '张芳',  '挂号员'),
('shoufei', '123456', '李强',  '收费员'),
('admin',   '123456', '王管理', '管理员');

-- ---------------------- 科室 ----------------------
INSERT INTO department (dept_code, dept_name, dept_type, location) VALUES
('DEPT01', '内科',   '门诊', '门诊楼2层'),
('DEPT02', '外科',   '门诊', '门诊楼3层'),
('DEPT03', '儿科',   '门诊', '门诊楼1层'),
('DEPT04', '妇科',   '门诊', '门诊楼3层'),
('DEPT05', '急诊科', '急诊', '急诊楼1层');

-- ---------------------- 医生 ----------------------
INSERT INTO doctor (doctor_code, doctor_name, dept_id, title, gender) VALUES
('D001', '张伟', 1, '主任医师',   '男'),
('D002', '李娜', 1, '副主任医师', '女'),
('D003', '王强', 2, '主治医师',   '男'),
('D004', '孙磊', 2, '主任医师',   '男'),
('D005', '赵敏', 3, '副主任医师', '女'),
('D006', '周涛', 3, '主治医师',   '男'),
('D007', '陈静', 4, '主任医师',   '女'),
('D008', '吴敏', 4, '主治医师',   '女'),
('D009', '刘洋', 5, '主治医师',   '男'),
('D010', '郑凯', 5, '副主任医师', '男');

-- ---------------------- 号别 ----------------------
INSERT INTO registration_level (level_code, level_name, reg_fee, diagnosis_fee) VALUES
('LV01', '普通门诊', 5.0,  5.0),
('LV02', '专家门诊', 20.0, 10.0),
('LV03', '急诊',     10.0, 10.0),
('LV04', '专病门诊', 15.0, 10.0);

-- ---------------------- 患者门诊档案 ----------------------
INSERT INTO patient (medical_record_no, name, gender, birth_date, id_card, phone, address, patient_type, insurance_no) VALUES
('MR202609230001', '刘建国', '男', '1978-03-12', '110101197803120011', '13800000001', '北京市朝阳区', '医保',   'YB1000001'),
('MR202609230002', '陈晓梅', '女', '1985-07-25', '110101198507250022', '13800000002', '北京市海淀区', '自费',   NULL),
('MR202609230003', '王大力', '男', '1992-11-08', '110101199211080033', '13800000003', '北京市西城区', '新农合', NULL),
('MR202609230004', '赵丽丽', '女', '2001-02-14', '110101200102140044', '13800000004', '北京市东城区', '自费',   NULL),
('MR202609230005', '孙志强', '男', '1966-09-30', '110101196609300055', '13800000005', '北京市丰台区', '医保',   'YB1000005'),
('MR202609230006', '周小燕', '女', '2015-05-18', '110101201505180066', '13800000006', '北京市石景山区', '自费',  NULL),
('MR202609230007', '吴国华', '男', '1959-12-01', '110101195912010077', '13800000007', '北京市通州区', '医保',   'YB1000007'),
('MR202609230008', '郑雨欣', '女', '2010-08-22', '110101201008220088', '13800000008', '北京市昌平区', '新农合', NULL);

-- ---------------------- 医生排班（今天） ----------------------
INSERT INTO doctor_schedule (doctor_id, dept_id, work_date, time_period, level_id, total_quota, used_quota, status) VALUES
(1,  1, date('now', 'localtime'), '上午', 1, 30, 0, '正常'),
(2,  1, date('now', 'localtime'), '上午', 2, 15, 0, '正常'),
(3,  2, date('now', 'localtime'), '上午', 1, 25, 0, '正常'),
(5,  3, date('now', 'localtime'), '上午', 2, 12, 0, '正常'),
(7,  4, date('now', 'localtime'), '下午', 1, 20, 0, '正常'),
(9,  5, date('now', 'localtime'), '夜班', 3, 40, 0, '正常'),
(1,  1, date('now', 'localtime'), '下午', 1, 30, 0, '正常'),
(4,  2, date('now', 'localtime'), '下午', 2, 15, 0, '正常'),
(5,  3, date('now', 'localtime'), '下午', 1, 20, 0, '正常'),
(2,  1, date('now', 'localtime'), '下午', 2, 15, 0, '正常'),
(7,  4, date('now', 'localtime'), '上午', 1, 20, 0, '正常'),
(4,  2, date('now', 'localtime'), '上午', 4, 10, 0, '停诊');

-- ---------------------- 医生排班（明天，用于预约演示） ----------------------
INSERT INTO doctor_schedule (doctor_id, dept_id, work_date, time_period, level_id, total_quota, used_quota, status) VALUES
(1, 1, date('now', '+1 day', 'localtime'), '上午', 1, 30, 0, '正常'),
(2, 1, date('now', '+1 day', 'localtime'), '上午', 2, 15, 0, '正常'),
(7, 4, date('now', '+1 day', 'localtime'), '上午', 1, 20, 0, '正常');

-- ---------------------- 挂号记录 ----------------------
-- schedule 1 (内科 张伟 上午 普通) 3 人
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A001', 1, 1, 1, 1, 1, '现场', 1, '已就诊', 10.0, 1),
('GH20260923A002', 2, 1, 1, 1, 1, '现场', 2, '已就诊', 10.0, 1),
('GH20260923A003', 3, 1, 1, 1, 1, '现场', 3, '已挂号', 10.0, 1);
-- schedule 2 (内科 李娜 上午 专家) 2 人
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A004', 4, 1, 2, 2, 2, '现场', 1, '已挂号', 30.0, 1),
('GH20260923A005', 5, 1, 2, 2, 2, '现场', 2, '已就诊', 30.0, 1);
-- schedule 3 (外科 王强 上午 普通) 1 人（已退号）
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A006', 6, 2, 3, 3, 1, '现场', 1, '已退号', 10.0, 1);
-- schedule 4 (儿科 赵敏 上午 专家) 2 人
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A007', 7, 3, 5, 4, 2, '现场', 1, '已挂号', 30.0, 1),
('GH20260923A008', 8, 3, 5, 4, 2, '预约', 2, '已挂号', 30.0, 1);
-- schedule 5 (妇科 陈静 下午 普通)
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A009', 1, 4, 7, 5, 1, '现场', 1, '已挂号', 10.0, 1);
-- schedule 6 (急诊科 刘洋 夜班 急诊)
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A010', 2, 5, 9, 6, 3, '现场', 1, '已挂号', 20.0, 1);
-- schedule 7 (内科 张伟 下午 普通)
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A011', 3, 1, 1, 7, 1, '现场', 1, '已挂号', 10.0, 1);
-- schedule 8 (外科 孙磊 下午 专家)
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A012', 4, 2, 4, 8, 2, '现场', 1, '已挂号', 30.0, 1);
-- schedule 10 (内科 李娜 下午 专家)
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A013', 6, 1, 2, 10, 2, '预约', 1, '已挂号', 30.0, 1);
-- schedule 11 (妇科 陈静 上午 普通)
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A014', 7, 4, 7, 11, 1, '现场', 1, '已就诊', 10.0, 1);
-- schedule 12 (外科 孙磊 上午 专病) - 停诊前预约
INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, level_id, reg_type, queue_no, status, fee, operator_id) VALUES
('GH20260923A015', 8, 2, 4, 12, 4, '预约', 1, '已挂号', 25.0, 1);

-- ---------------------- 收费记录 ----------------------
INSERT INTO payment (reg_id, amount, pay_type, status, operator_id) VALUES
(1,  10.0, '医保',   '已支付', 2),
(2,  10.0, '现金',   '已支付', 2),
(3,  10.0, '微信',   '已支付', 2),
(4,  30.0, '现金',   '已支付', 2),
(5,  30.0, '医保',   '已支付', 2),
(7,  30.0, '支付宝', '已支付', 2),
(9,  10.0, '现金',   '已支付', 2),
(10, 20.0, '现金',   '已支付', 2),
(11, 10.0, '微信',   '已支付', 2),
(12, 30.0, '医保',   '已支付', 2),
(14, 10.0, '现金',   '已支付', 2),
(15, 25.0, '现金',   '已支付', 2);

-- ---------------------- 同步排班已用号源 ----------------------
-- 已用号源 = 该排班下未退号的挂号数量
UPDATE doctor_schedule
SET used_quota = (
    SELECT COUNT(*)
    FROM registration r
    WHERE r.schedule_id = doctor_schedule.schedule_id
      AND r.status <> '已退号'
);

-- ---------------------- 操作日志 ----------------------
INSERT INTO operation_log (user_id, action, target, detail) VALUES
(1, '建档', 'patient:MR202609230001', '新建门诊档案 刘建国'),
(1, '挂号', 'reg:GH20260923A001', '内科/张伟/普通门诊'),
(1, '退号', 'reg:GH20260923A006', '患者 周小燕 退号'),
(2, '收费', 'reg:GH20260923A003', '微信支付 10.00 元');
