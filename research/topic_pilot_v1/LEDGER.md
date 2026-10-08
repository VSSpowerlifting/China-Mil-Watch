# Regional Topic Taxonomy v1 — provisional review ledger

Generated from `ledger.json` by `python3 scripts/topic_pilot.py --report`.

**All labels are Codex proposals pending human review. No assignments are applied.**

## Sample

| Desk | Records |
|---|---:|
| china | 24 |
| indonesia | 3 |
| japan | 5 |
| korea | 3 |
| philippines | 7 |
| singapore | 12 |
| vietnam | 6 |

36 production / 24 shadow; 16 topics proposed; 15 unclassified; 28 multi-label; 30 cases flagged for review.

## Topic distribution (record counts; topics overlap)

| Topic | Proposed records |
|---|---:|
| `military_exercises` | 17 |
| `force_posture_basing` | 7 |
| `maritime_security` | 8 |
| `gray_zone_coast_guard` | 1 |
| `defense_diplomacy` | 7 |
| `alliances_partnerships` | 11 |
| `procurement_acquisition` | 2 |
| `defense_industry` | 3 |
| `emerging_technology` | 7 |
| `nuclear_deterrence` | 2 |
| `cyber_information` | 7 |
| `space_security` | 0 |
| `taiwan_strait` | 1 |
| `south_china_sea` | 3 |
| `east_china_sea` | 0 |
| `economic_security` | 5 |
| `export_controls_sanctions` | 0 |
| `critical_minerals_supply_chains` | 3 |
| `doctrine_strategy` | 2 |

## P01 · china · production

南部战区新闻发言人发表谈话

[Source](http://www.81.cn/yw_208727/16491198.html) · source-stated date `2026-10-05`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16491198.html`.

Body SHA-256: `bc87b38c83f5a0f8b6ad42e5d0c0c3db20146f96038af352a3536f7bf6239549` (171 characters).

Existing desk labels: `south_china_sea`, `coast_guard`.

- Propose `maritime_security` [E1]: Source describes a maritime-area military interception.

- Propose `south_china_sea` [E2]: Scarborough/Huangyan sovereignty dispute is substantive.

E1 · `text_original[34:140]` (Unicode characters, end exclusive):

> 8型机未经中国政府批准，非法侵入中国黄岩岛领空。中国人民解放军南部战区组织海空兵力，依法依规跟踪监视、警告驱离。黄岩岛是中国固有领土。菲方行为严重侵犯中国主权，极易引发海空意外事件。我们正告菲方立即停止侵权挑衅。

E2 · `text_original[17:120]` (Unicode characters, end exclusive):

> 示，10月3日，菲律宾1架C-208型机未经中国政府批准，非法侵入中国黄岩岛领空。中国人民解放军南部战区组织海空兵力，依法依规跟踪监视、警告驱离。黄岩岛是中国固有领土。菲方行为严重侵犯中国主权，极易引发海空

Review question/limitation: Local coast_guard label is not evidence of coast-guard involvement: this body identifies PLA forces. Do not copy it.

## P02 · china · production

参加俄罗斯“中部-二〇二六”战略演习实兵演练侧记

[Source](http://www.81.cn/yw_208727/16491052.html) · source-stated date `2026-10-04`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16491052.html`.

Body SHA-256: `20804fd3ff51120c16ba0bdf08acfdc9dd38d826c98484cd538220b17639ae6a` (1215 characters).

Existing desk labels: `exercises`, `military_diplomacy`.

- Propose `military_exercises` [E1]: Named multinational field exercise.

- Propose `emerging_technology` [E2]: Uncrewed systems are discussed as a substantive operational feature.

E1 · `text_original[0:99]` (Unicode characters, end exclusive):

> 风雨激战切巴尔库尔 ——参加俄罗斯“中部-二〇二六”战略演习实兵演练侧记 ■解放军报记者 张科进 宋子洵 特约记者 康 克 当地时间10月2日下午，俄罗斯“中部-2026”战略演习在俄罗斯车里雅宾斯

E2 · `text_original[1015:1123]` (Unicode characters, end exclusive):

> 行进边打击，战斗协同精确到秒，战场衔接分毫不差。 近距离观摩这场演习，无人装备的大规模、全过程应用让记者大开眼界。战斗中，低空一直被各型无人机占据，“嗡嗡”声不绝于耳；各种无人战斗车辆经过加改装，广泛应用于火力打击、

Review question/limitation: Exercise and technology may co-occur; participating countries alone do not justify alliances_partnerships.

## P03 · china · production

长剑倚天向战行——火箭军某部官兵节日期间坚守战位见闻

[Source](http://www.81.cn/yw_208727/16491129.html) · source-stated date `2026-10-05`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16491129.html`.

Body SHA-256: `1edc7f342d03e5f3a8db8b6c86f489fff4760e48632b726164e384e29fdb6d7e` (1056 characters).

Existing desk labels: `exercises`, `nuclear`.

- Propose `military_exercises` [E1]: Identifiable simulated-launch training.

E1 · `text_original[199:303]` (Unicode characters, end exclusive):

> 们越要绷紧战备弦，以战斗姿态守护祖国安宁！”张班长简短动员后，一场融合模拟发射和原理串讲的训练紧张展开。 “号手就位！”随着口令声下达，官兵迅速奔向各自战位。 “与营指挥所通信中断，立即处置！”特情突至，二级

Review question/limitation: Local nuclear label and Rocket Force identity do not establish nuclear-specific content; withhold nuclear_deterrence.

## P04 · china · production

在习近平强军思想指引下·奋进强军路 打好攻坚战｜在数智云端“铺路架桥”

[Source](http://www.mod.gov.cn/gfbw/wzll/yw_214068/16491149.html) · source-stated date `2026-10-05`

Record identity: `china` / `mod_china` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.mod.gov.cn/gfbw/wzll/yw_214068/16491149.html`.

Body SHA-256: `b0d45e3a27a3915cb06de5649392a74ce0de350520efa2544ad56e1f9135ecbc` (4192 characters).

Existing desk labels: `exercises`, `modernization`, `doctrine`.

- Propose `cyber_information` [E1]: Operational military information-network capability.

- Propose `military_exercises` [E2]: Network support during an identifiable joint training event.

E1 · `text_original[405:511]` (Unicode characters, end exclusive):

> ，该部官兵以攻坚姿态推进转型，加快建设符合现代战争要求、具有我军特色的网络信息体系，在昆仑雪线上织出一张数据赋能的信息“天网”。 翻过思想“达坂”，立起打仗思维 夜已深，该部某维护分中心值班大厅内依旧一派忙碌景象

E2 · `text_original[24:132]` (Unicode characters, end exclusive):

> 的观察报告 ■张大鹏 王石萌 解放军报记者 李蕾 深夜，喀喇昆仑，一场多军兵种联合训练进入关键阶段。 千里之外，信息支援部队某部某维护分中心值班大厅内，告警声骤然响起——某重要用户主用链路中断，备用链路同时告急。 大

Review question/limitation: cyber_information encompasses information-network support as well as offensive cyber; review breadth, not presumed cyberattack.

## P05 · china · production

俄罗斯向北约发出“核警告”有何考量

[Source](https://www.news.cn/milpro/20261001/f58cffe51ef64573bde27441efb513ec/c.html) · source-stated date `2026-10-01`

Record identity: `china` / `xinhua_mil` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.news.cn/milpro/20261001/f58cffe51ef64573bde27441efb513ec/c.html`.

Body SHA-256: `01a5396a902d04021c3e5a9a3cab3f8928d9d658de06a6b3e41fbf2a8992cd72` (1428 characters).

Existing desk labels: none recorded.

- Propose `nuclear_deterrence` [E1]: Reports explicit nuclear signaling; this is a China-source report about Russia, not a Russia Desk record.

E1 · `text_original[60:165]` (Unicode characters, end exclusive):

> 的海地区军事活动发出严厉警告，称如果北约封锁加里宁格勒州，俄方准备动用包括核武器在内的一切手段保卫领土。北约秘书长吕特9月30日回应称，北约是“防御性联盟”，并谴责俄方“核威胁”。 加里宁格勒州发生了什么？北约

Review question/limitation: Subject geography differs from desk ownership. Keep this as a China-source record; it is a regional-scope negative control.

## P06 · china · production

外交部：国际社会应敦促日本恪守“无核三原则”

[Source](http://www.81.cn/fyr/16490654.html) · source-stated date `2026-09-30`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/fyr/16490654.html`.

Body SHA-256: `c5c1a58a964a694bf2bdc0913e7a143fd8fb378c4f85c17b9b927ee93f9450ad` (748 characters).

Existing desk labels: none recorded.

- Propose `nuclear_deterrence` [E1]: Nuclear policy and nonproliferation obligations are substantive.

E1 · `text_original[92:197]` (Unicode characters, end exclusive):

> 挑衅和公然践踏，再次暴露日本右翼势力拥核企图。国际社会应敦促日本恪守“无核三原则”，严格履行《不扩散核武器条约》义务。 当日例行记者会上，有记者问：据报道，日本防卫大臣小泉进次郎28日表示，在修订“安保三文件”

## P07 · china · production

强军论坛｜筑牢智能时代的网络安全防线

[Source](http://www.81.cn/yw_208727/16486191.html) · source-stated date `2026-09-14`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16486191.html`.

Body SHA-256: `e0996b5e3192d0116a9c1388c0de9a68da290f25f8a6649b4838e278ec10761d` (1246 characters).

Existing desk labels: `doctrine`, `cyber_info`, `political_work`.

- Propose `cyber_information` [E1]: Military cybersecurity risks and safeguards.

E1 · `text_original[279:385]` (Unicode characters, end exclusive):

> 主席深刻指出：“没有网络安全就没有国家安全，没有信息化就没有现代化。”军营网络安全是国家网络安全的重要组成部分，事关政治安全和意识形态安全，事关部队战斗力建设，网络安全问题已成为全军面临的最复杂、最现实、最严峻的

Review question/limitation: Defensive cyber hygiene versus operations: existing definition admits security-relevant cyber activity, but title could mislead.

## P08 · china · production

商务部回应美发布中国人工智能企业对美蒸馏活动相关网络安全公告

[Source](http://www.81.cn/fyr/16484734.html) · source-stated date `2026-09-09`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/fyr/16484734.html`.

Body SHA-256: `7a2756958d5e8ddbbe30df868df021acb94536c5da762c950615d9ee4b32e779` (1106 characters).

Existing desk labels: none recorded.

- Propose `cyber_information` [E1]: Security-agency cybersecurity advisory and the attributed Chinese response.

- Propose `economic_security` [E2]: Source explicitly links technology-sector interests with national security.

E1 · `text_original[6:112]` (Unicode characters, end exclusive):

> 月9日电 商务部新闻发言人9日就美发布中国人工智能企业对美蒸馏活动相关网络安全公告答记者问时表示，中方认为，美方所谓中国人工智能企业从事“工业规模”蒸馏美模型的指控，于事无凭，于法无据。美方此举，是将蒸馏这一业内

E2 · `text_original[609:718]` (Unicode characters, end exclusive):

> 以打击蒸馏为名，行产业垄断之实。美方由安全部门发布公告，是将个别企业和资本利益与国家安全相捆绑，动用国家强权机构干涉正常商业活动。我们注意到，美个别人工智能企业滥用竞争优势地位，在用户协议中设置宽泛的地域限制等霸王条款

Review question/limitation: A cybersecurity advisory is not an export control or sanction. Technology-statecraft overlap needs reviewer adjudication.

## P09 · china · production

两栖无人装备：抢滩登陆的“机甲先锋”

[Source](http://www.81.cn/yw_208727/16482936.html) · source-stated date `2026-09-02`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16482936.html`.

Body SHA-256: `01d64822aa6b2732d057897ef9634e9c8dd79481df4d0927c5d8d47b2139a6d6` (3204 characters).

Existing desk labels: `taiwan`, `modernization`, `doctrine`.

- Propose `emerging_technology` [E1]: Substantive development of autonomous amphibious capability.

E1 · `text_original[44:150]` (Unicode characters, end exclusive):

> 耳其“泰克诺费斯特蓝色祖国”活动中，该国FNSS公司的8吨级U-MAV无人两栖战车正式亮相，成为重型两栖无人装备发展的新注脚。 这种技术演进并非孤例。数月前，美国海军陆战队曾在彭德尔顿营的测试中，验证“蜂群”无人

## P10 · china · production

“自由轮”：用工业速度赢得胜利的“丑小鸭”

[Source](http://www.81.cn/yw_208727/16482944.html) · source-stated date `2026-09-02`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16482944.html`.

Body SHA-256: `dfe9d143ab1a7f4b2dbd4ad5d82530c4ec76177dd62b7487417478891df360f5` (1235 characters).

Existing desk labels: none recorded.

- Propose `defense_industry` [E1]: Wartime shipbuilding production methods; historical analytical subject, not a current procurement event.

E1 · `text_original[503:607]` (Unicode characters, end exclusive):

> 少工时，将最多物资送到前线。 真正让“自由轮”载入史册的，是其革命性的建造方式。美国船厂大规模引入分段建造法和焊接技术，来取代耗时费力的传统铆接工艺：将船体切分成数百个预制单元，各工厂同步生产，最终像拼图般在

Review question/limitation: Historical wartime merchant shipping versus defense-industry scope needs adjudication; do not count this as current acquisition.

## P11 · china · production

中国海警位中国台湾岛以东海域依法开展常态化执法巡查

[Source](http://www.81.cn/yw_208727/16490222.html) · source-stated date `2026-09-29`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16490222.html`.

Body SHA-256: `852092ac1947c6b0723a11c6301fc42eb68b366e3a41c4b8a5fa91f1e71c6c0e` (1051 characters).

Existing desk labels: `taiwan`, `coast_guard`.

- Propose `taiwan_strait` [E1]: Cross-strait sovereignty and patrol posture are the subject.

- Propose `maritime_security` [E2]: Maritime patrol activity.

- Propose `gray_zone_coast_guard` [E3]: Security-relevant coast-guard patrol framed by the source as sovereignty enforcement.

E1 · `text_original[0:79]` (Unicode characters, end exclusive):

> 中国海警位中国台湾岛以东海域依法开展常态化执法巡查 China Coast Guard Conducts Routine Law-enforcement Pa

E2 · `text_original[0:90]` (Unicode characters, end exclusive):

> 中国海警位中国台湾岛以东海域依法开展常态化执法巡查 China Coast Guard Conducts Routine Law-enforcement Patrols in th

E3 · `text_original[142:252]` (Unicode characters, end exclusive):

>  with the Law 中国海警局新闻发言人姜略表示，9月29日，中国海警朱家尖舰编队位中国台湾岛以东海域依法开展常态化执法巡查。9月以来，朱家尖舰编队持续加强相关海域管控，有力保障正常航行和作业秩序，切实维护包括台

Review question/limitation: Coast-guard routine wording versus sovereignty/security significance requires review. East of Taiwan does not automatically mean east_china_sea.

## P12 · china · production

东海某海域，一场实战背景下的两栖攻击舰与气垫艇协同训练拉开战幕

[Source](http://www.mod.gov.cn/gfbw/wzll/hj/16486972.html) · source-stated date `2026-09-17`

Record identity: `china` / `mod_china` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.mod.gov.cn/gfbw/wzll/hj/16486972.html`.

Body SHA-256: `cfa90c466509c1af6f5fec68f3e41d3b568f05d449719df2a89c4014c5ea2d7c` (807 characters).

Existing desk labels: `east_china_sea`, `exercises`, `modernization`.

- Propose `military_exercises` [E1]: Identifiable naval ship-to-craft training.

- Propose `maritime_security` [E2]: Substantive naval operational activity.

E1 · `text_original[0:91]` (Unicode characters, end exclusive):

> “野马”蹈海 踏浪飞驰 ——海军某部组织舰艇协同训练见闻 初秋，东海某海域，海军某部两栖攻击舰耕波犁浪，向预定海域航渡。坞舱内，气垫艇蓄势待发，一场实战背景下的两栖攻击舰与气垫艇协同

E2 · `text_original[7:112]` (Unicode characters, end exclusive):

> 踏浪飞驰 ——海军某部组织舰艇协同训练见闻 初秋，东海某海域，海军某部两栖攻击舰耕波犁浪，向预定海域航渡。坞舱内，气垫艇蓄势待发，一场实战背景下的两栖攻击舰与气垫艇协同训练拉开战幕。 “气垫艇进出坞部署！”指令

Review question/limitation: East China Sea is the event location; substantive flashpoint content is absent. Withhold east_china_sea.

## P13 · china · production

钧声｜以坚决行动遏制菲方祸乱南海的恶劣行径

[Source](http://www.81.cn/yw_208727/16489796.html) · source-stated date `2026-09-28`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16489796.html`.

Body SHA-256: `e8269b49917595a3a581678e55ca13c6fa5c4650c54744d4a3a31bdbfdb0e02b` (1372 characters).

Existing desk labels: `south_china_sea`, `exercises`, `doctrine`, `coast_guard`.

- Propose `military_exercises` [E1]: Named-area joint exercise.

- Propose `south_china_sea` [E2]: Disputed regional security is central.

- Propose `maritime_security` [E3]: Maritime-area military activity.

E1 · `text_original[0:99]` (Unicode characters, end exclusive):

> 9月27日，中国人民解放军南部战区位黄岩岛周边海空域组织海空联合演训，这是针对菲律宾破坏南海地区和平稳定的必要行动和严正警告。中国人民解放军时刻保持高度戒备，以坚决行动遏制菲方祸乱南海的恶劣行径，坚

E2 · `text_original[7:117]` (Unicode characters, end exclusive):

> 国人民解放军南部战区位黄岩岛周边海空域组织海空联合演训，这是针对菲律宾破坏南海地区和平稳定的必要行动和严正警告。中国人民解放军时刻保持高度戒备，以坚决行动遏制菲方祸乱南海的恶劣行径，坚决捍卫国家主权、安全、发展利益。 近

E3 · `text_original[0:91]` (Unicode characters, end exclusive):

> 9月27日，中国人民解放军南部战区位黄岩岛周边海空域组织海空联合演训，这是针对菲律宾破坏南海地区和平稳定的必要行动和严正警告。中国人民解放军时刻保持高度戒备，以坚决行动遏制菲方祸乱南

## P14 · china · production

【双语】国防部敦促日方停止在南海问题上搬弄是非

[Source](http://www.81.cn/yw_208727/16488940.html) · source-stated date `2026-09-24`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16488940.html`.

Body SHA-256: `ca2402e86ec50e8052a212de977d01150c98836b184f0cf15a60485cd21e1231` (1894 characters).

Existing desk labels: `south_china_sea`, `east_china_sea`, `military_diplomacy`.

- Propose `south_china_sea` [E1]: Official response about a regional dispute.

- Propose `maritime_security` [E2]: Maritime vessel incident is substantively discussed.

E1 · `text_original[0:79]` (Unicode characters, end exclusive):

> 国防部敦促日方停止在南海问题上搬弄是非 MND Urges the Japanese Side to Stop Sowing Discord in the S

E2 · `text_original[104:207]` (Unicode characters, end exclusive):

> 部举行例行记者会，国防部新闻发言人蒋斌大校答记者问。 记者：菲律宾一艘公务船在中国南沙群岛仙宾礁附近海域挑衅滋事，事情发生后日本驻菲律宾大使馆迅速在社交平台发文，对中方“采取危险行动”“深表关切”，还自我标

## P15 · china · production

携手砺精兵 并肩卫和平——专访中方参加俄罗斯“中部-2026”战略演习部队指挥员

[Source](http://www.81.cn/yw_208727/16490925.html) · source-stated date `2026-10-03`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16490925.html`.

Body SHA-256: `ae69bf60facec449c79c8ffb23ec91119fa769517cd59e72c8554ee44ad8d04e` (1789 characters).

Existing desk labels: `exercises`, `military_diplomacy`.

- Propose `military_exercises` [E1]: Named exercise.

- Propose `alliances_partnerships` [E2]: Recurring military cooperation mechanisms are substantively described.

E1 · `text_original[0:101]` (Unicode characters, end exclusive):

> 携手砺精兵 并肩卫和平 ——专访中方参加俄罗斯“中部-2026”战略演习部队指挥员 ■解放军报记者 张科进 宋子洵 特约记者 康克 组织联合突击。付超 摄 9月中旬至10月上旬，我军派出部队参加俄罗斯“

E2 · `text_original[282:392]` (Unicode characters, end exclusive):

> 密切，联合演习、海空巡航常态化开展，后勤、院校、军兵种交往、人员培训等专业领域合作持续拓展，充分体现了两国关系的高水平与特殊性，为促进两国国防和军队发展、塑造有利周边态势发挥了积极作用。今年，根据中俄双方事先达成的共识和

Review question/limitation: Exercise cooperation versus durable partnership: proposal relies on described recurring mechanisms, not country co-mention.

## P16 · china · production

中老“和平列车-2026”人道主义医学救援联合演习暨医疗服务活动纪事

[Source](http://www.81.cn/yw_208727/16490084.html) · source-stated date `2026-09-29`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16490084.html`.

Body SHA-256: `e7d0bcbc1f1bffb88a69b679fa9a51ed205d8ecfbe0fe545663cf19e71a41d85` (1345 characters).

Existing desk labels: `exercises`, `military_diplomacy`.

- Propose `military_exercises` [E1]: Named humanitarian medical exercise.

- Propose `defense_diplomacy` [E2]: Military-to-military cooperation through medical services.

E1 · `text_original[0:104]` (Unicode characters, end exclusive):

> 占芭花常开 兄弟情常在 ——中老“和平列车-2026”人道主义医学救援联合演习暨医疗服务活动纪事 ■刘小薇 杨 超 近日，随着我军卫生列车驶离老挝万象，穿越中老铁路“友谊隧道”，驶入云南磨憨口岸，为期17天的

E2 · `text_original[154:262]` (Unicode characters, end exclusive):

> 训场内通力协作、密切配合，在医疗服务中探讨新兴技术应用、交流疑难病例。中老两军卫勤力量以精湛医术与赤诚仁心，把守望相助的深情写在绵延铁路上。 占芭花常开，兄弟情常在。从2017年到2026年，“和平列车”医疗队六度奔

Review question/limitation: Humanitarian assistance is central but has no dedicated topic; training/cooperation labels capture only part of the subject.

## P17 · china · production

无人作战能力成为法军建设重点

[Source](http://www.81.cn/yw_208727/16487901.html) · source-stated date `2026-09-21`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16487901.html`.

Body SHA-256: `14c3b2799008e1055b7c91210f110396224f05b2e276e16a53d3dbde460b6f04` (1334 characters).

Existing desk labels: `modernization`, `doctrine`, `military_diplomacy`.

- Propose `emerging_technology` [E1]: Uncrewed capability development.

- Propose `doctrine_strategy` [E2]: Force organization and strategic autonomy are substantively analyzed.

E1 · `text_original[0:100]` (Unicode characters, end exclusive):

> 无人作战能力成为法军建设重点 ■许芳铭 近年来，法国将无人作战能力建设作为填补安全真空、践行战略自主的重要抓手。其核心目的是要在确保技术主权的前提下，以智能化、集群化突破传统战力瓶颈，构建高度协同、快

E2 · `text_original[11:115]` (Unicode characters, end exclusive):

> 设重点 ■许芳铭 近年来，法国将无人作战能力建设作为填补安全真空、践行战略自主的重要抓手。其核心目的是要在确保技术主权的前提下，以智能化、集群化突破传统战力瓶颈，构建高度协同、快速响应的无人作战体系，以维持其

## P18 · china · production

东部战区海军某旅紧贴实战需求展开技术攻关——深山台站实现无人值守

[Source](http://www.mod.gov.cn/gfbw/wzll/hj/16488209.html) · source-stated date `2026-09-22`

Record identity: `china` / `mod_china` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.mod.gov.cn/gfbw/wzll/hj/16488209.html`.

Body SHA-256: `e97b4e7f793c799308946f96eeafb501f4d677a409aafac53fdd9c29b971721a` (1204 characters).

Existing desk labels: `exercises`, `modernization`, `cyber_info`.

- Propose `cyber_information` [E1]: Electronic-warfare capability.

- Propose `military_exercises` [E2]: Identifiable electromagnetic opposing-force training.

- Propose `emerging_technology` [E3]: Remote uncrewed electronic-warfare systems.

E1 · `text_original[60:168]` (Unicode characters, end exclusive):

> ，操作号手敲击键盘，一道道指令瞬间传送至数公里外分散布设的无人干扰站。多站协同干扰压制，“敌”通信信号眨眼之间被切断。 从过去“守着装备转”到如今“盯着屏幕战”，这一变化得益于该旅探索推行的装备值守新模式。 该旅领导

E2 · `text_original[11:115]` (Unicode characters, end exclusive):

> 战需求展开技术攻关—— 山地密林，东部战区海军某旅一场复杂电磁环境下的对抗训练紧张进行。指挥方舱内，操作号手敲击键盘，一道道指令瞬间传送至数公里外分散布设的无人干扰站。多站协同干扰压制，“敌”通信信号眨眼之间

E3 · `text_original[54:159]` (Unicode characters, end exclusive):

> 。指挥方舱内，操作号手敲击键盘，一道道指令瞬间传送至数公里外分散布设的无人干扰站。多站协同干扰压制，“敌”通信信号眨眼之间被切断。 从过去“守着装备转”到如今“盯着屏幕战”，这一变化得益于该旅探索推行的装备值守

## P19 · china · production

海军航空大学某团创新教官机型改装训练模式——“装备空窗期”成为“能力加速期”

[Source](http://www.mod.gov.cn/gfbw/wzll/kj/16487888.html) · source-stated date `2026-09-21`

Record identity: `china` / `mod_china` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.mod.gov.cn/gfbw/wzll/kj/16487888.html`.

Body SHA-256: `fd01ba0ee0442a750ca37acc2c2f1b84acf65ec8724c7623e540a59ed9c63d50` (5562 characters).

Existing desk labels: `exercises`, `modernization`, `doctrine`.

- Propose `military_exercises` [E1]: Aircraft-conversion flight training.

E1 · `text_original[36:142]` (Unicode characters, end exclusive):

> 海军航空大学某团机场，迎来了第二批前来改装新机的飞行教官，开展改装后的首次飞行训练。 “计时起飞！”随着塔台指挥员指令下达，数架战机依次升空。与以往新教官改装不同的是，这批曾执教某型教练机多年的改装飞行教官，首次

Review question/limitation: Aircraft-conversion training is not an acquisition decision. Withhold procurement_acquisition despite local modernization.

## P20 · china · production

及时“咬咬”耳朵、扯扯袖子——推动学习贯彻习近平党建思想走深走实系列谈⑩

[Source](http://www.81.cn/yw_208727/16491218.html) · source-stated date `2026-10-06`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16491218.html`.

Body SHA-256: `e8f642f6dcded6bbcd1dbf7767e695c84e9a11accd58e53a4422c818e30bacc0` (1701 characters).

Existing desk labels: none recorded.

Unclassified: Party discipline and political education do not establish force-employment doctrine.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 及时“咬咬”耳朵、扯扯袖子 ——推动学习贯彻习近平党建思想走深走实系列谈⑩ ■顺 亮 中秋国庆双节之际，不少单位以短信、倡议、教育等方式，提醒广大官兵严守廉洁规定、严防违规行为，过一个风清气正的假期。这种提醒，及时到位，充满温情，是爱护，也是帮助。 生活中，我

## P21 · china · production

国庆坚守战位，武警官兵担负巡逻执勤任务守护群众平安

[Source](http://www.81.cn/wj_208567/16491191.html) · source-stated date `2026-10-05`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/wj_208567/16491191.html`.

Body SHA-256: `8000f6d67bfedb2b6cba7fa30e2b11c76370fd985b33ce3acc8ea13513d9d86c` (214 characters).

Existing desk labels: none recorded.

Unclassified: Domestic holiday policing is not maritime gray-zone activity or a military exercise.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 国庆佳节，处处洋溢着喜庆的节日氛围。武警广西总队河池支队官兵坚守战位，在河池西站及驻地商圈等人流密集区域，与公安民警开展联勤武装巡逻，全力维护驻地秩序、守护群众平安过节。 巡逻中，武警官兵采取“步巡+车巡”相结合、定点警戒与动态巡控相结合的模式，科学统筹执勤力

## P22 · china · production

神舟二十三号航天员视频祝福祖国 祝福中国航天事业再创辉煌

[Source](http://www.81.cn/yw_208727/16490762.html) · source-stated date `2026-10-01`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16490762.html`.

Body SHA-256: `404ec59364cb3191133e3f1c5c0c821d2703b08ead0b331ccacf7c202458fea4` (628 characters).

Existing desk labels: `modernization`.

Unclassified: Astronaut holiday greetings do not establish substantive space-security content.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 新华社北京10月1日电（李国利、邓孟）10月1日，新中国迎来77岁生日。举国欢庆的时刻，正在中国空间站执行任务的神舟二十三号航天员乘组，向伟大祖国送上来自苍穹的特别祝福。 身处约400公里外的太空家园，朱杨柱、张志远、黎家盈3名航天员心里对祖国家园始终念念不忘

## P23 · china · production

我国首届航天医学工程大会召开

[Source](http://www.81.cn/yw_208727/16488441.html) · source-stated date `2026-09-23`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16488441.html`.

Body SHA-256: `c989ab4f401729d10a92ac1a73038ce5ae14566d56e384b9ef687a095347f7cc` (442 characters).

Existing desk labels: `modernization`.

Unclassified: Space medicine conference has no established security nexus in the text.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 我国首届航天医学工程大会召开 解放军报讯 特约记者占康、记者李伟欣报道：9月19日至20日，我国首届航天医学工程大会在天津召开。大会以“铸人・铸器・智创未来”为主题，聚焦航天医学工程关键科学问题、技术创新与转化应用，为太空健康保障体系建设和深空探测发展提供新思

## P24 · china · production

八一锐评丨过节更须“守节”

[Source](http://www.81.cn/yw_208727/16491226.html) · source-stated date `2026-10-06`

Record identity: `china` / `pla_daily` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `http://www.81.cn/yw_208727/16491226.html`.

Body SHA-256: `9a7fecaacf9a3e341d867e17f82f20527c74e79e6f80b0707dbb94c0cce5bb08` (331 characters).

Existing desk labels: none recorded.

Unclassified: Holiday discipline exhortation is outside the v1 subject vocabulary.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 过节更须“守节” ■张迪 国庆长假，军队党员干部如何正确面对礼尚往来，走出“人情困境”？学会拒绝是一个好办法。 从近年来查处的各类违纪违法案件来看，“礼”的背后往往是“利”，节礼中可能暗藏着请托和攀附。一些党员干部正是在一瓶酒、一条烟等看似不起眼的“小意思”上

## P25 · singapore · production

Media Reply on PLAN Ships Docking at CNB

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/05oct26-mq/) · source-stated date `2026-10-05`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/05oct26-mq/`.

Body SHA-256: `f908abdc4d4759510a5188e970849f3407d9997d12d5ffc3e4bf2ad80139e251` (378 characters).

Existing desk labels: none recorded.

- Propose `force_posture_basing` [E1]: Port access for visiting warships.

E1 · `text_original[110:227]` (Unicode characters, end exclusive):

> re for a routine technical stop at Changi Naval Base. Singapore regularly facilitates transits, port calls, and stopo

Review question/limitation: A port visit fits access language; short visit should not imply persistent basing or deployment.

## P26 · singapore · production

Minister for Defence Chan Chun Sing Reaffirmed Warm and Friendly Bilateral Relationship with Qatar

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/4oct26-nr/) · source-stated date `2026-10-04`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/4oct26-nr/`.

Body SHA-256: `25278e0665e6abb8d65e63078b41f142635704d6d44a08a21b31afc1837e4cef` (1840 characters).

Existing desk labels: none recorded.

- Propose `defense_diplomacy` [E1]: Ministerial defense engagement.

- Propose `alliances_partnerships` [E2]: Formal defense relationship framework.

E1 · `text_original[16:140]` (Unicode characters, end exclusive):

> inister for Defence Chan Chun Sing met with his counterpart, Deputy Prime Minister and Minister of State for Defence Affairs

E2 · `text_original[1273:1399]` (Unicode characters, end exclusive):

> e framework of the Qatar-Singapore High-Level Joint Committee (HLJC). Minister Chan welcomed Qatar’s regular participation in 

## P27 · singapore · production

Fact Sheet: Offshore Patrol Vessels (OPVs)

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-fs/) · source-stated date `2026-10-02`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-fs/`.

Body SHA-256: `a7a5647f9a5062ec52e7e28538016b423d74c407e8ee188445885a117ee983bb` (4922 characters).

Existing desk labels: none recorded.

- Propose `procurement_acquisition` [E1]: Concrete new-vessel capability program.

- Propose `maritime_security` [E2]: Stated maritime-security mission.

E1 · `text_original[379:502]` (Unicode characters, end exclusive):

> iption of OPVs The Sentinel -class Offshore Patrol Vessels (OPVs) are Singapore Government Vessels purpose-built to meet th

E2 · `text_original[506:623]` (Unicode characters, end exclusive):

> creased demands and wider scope of maritime security operations. Signed between the Ministry of Defence and Fr. Fassm

Review question/limitation: Acquisition and maritime mission legitimately overlap; the platform name alone is insufficient for other naval topics.

## P28 · singapore · production

Minister for Defence Chan Chun Sing Officiates at the Launch Ceremony of the Singapore Navy’s First Offshore Patrol Vessel

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr/) · source-stated date `2026-10-02`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr/`.

Body SHA-256: `fc8fba52b8e07d5da932d232555e5d64ae083b44c346d6627a762c4864c45164` (4325 characters).

Existing desk labels: none recorded.

- Propose `procurement_acquisition` [E1]: Launch of a specific acquisition capability.

- Propose `defense_industry` [E2]: Named shipbuilder and vessel production.

- Propose `defense_diplomacy` [E3]: Bilateral defense engagement at the launch.

E1 · `text_original[431:559]` (Unicode characters, end exclusive):

> f the Republic of Singapore Navy’s first Offshore Patrol Vessel in Berne, Germany. German Federal Minister of Defence Boris Pist

E2 · `text_original[160:267]` (Unicode characters, end exclusive):

> rol Vessel (OPV), Sentinel, at the Fassmer shipyard in Berne, Germany, on 1 October 2026. The Republic of S

E3 · `text_original[479:613]` (Unicode characters, end exclusive):

> e Patrol Vessel in Berne, Germany. German Federal Minister of Defence Boris Pistorius delivering his speech at the launch of the Repub

Review question/limitation: Ceremonial launch and actual production/acquisition overlap. Check whether diplomatic engagement warrants a separate label.

## P29 · singapore · production

Singapore and Brunei Air Forces Launch Exercise Vanguard, Marking New Milestone in 50 Years of Defence Relations

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr2/) · source-stated date `2026-10-02`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr2/`.

Body SHA-256: `6ade2add7c9d738b63f6ee2b100b4d33d6f4bf67fc5d1cdab29232134d6fa224` (3427 characters).

Existing desk labels: none recorded.

- Propose `military_exercises` [E1]: Named bilateral exercise.

- Propose `alliances_partnerships` [E2]: Durable recurring exercise framework.

E1 · `text_original[91:208]` (Unicode characters, end exclusive):

> Brunei Air Force (RBAirF) launched Exercise Vanguard, a new overarching bilateral exercise framework to deepen cooper

E2 · `text_original[116:256]` (Unicode characters, end exclusive):

>  launched Exercise Vanguard, a new overarching bilateral exercise framework to deepen cooperation between both air forces. The Republic of S

## P30 · singapore · production

Singapore Navy Participates in 2026 ASEAN Maritime Exercises

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr3/) · source-stated date `2026-10-02`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr3/`.

Body SHA-256: `ced43fd969de5301f2297ec64867b7a2a88e2870b071d743a540ac1e1cb2ef77` (4095 characters).

Existing desk labels: none recorded.

- Propose `military_exercises` [E1]: Named exercise.

- Propose `maritime_security` [E2]: Maritime security cooperation is explicit.

E1 · `text_original[41:170]` (Unicode characters, end exclusive):

> Navy (RSN) participated in the 2nd ASEAN-India Maritime Exercise (AIME) from 28 September to 2 October 2026, and the ASEAN Defenc

E2 · `text_original[199:316]` (Unicode characters, end exclusive):

> MM-Plus) Experts’ Working Group on Maritime Security (EWG-MS) Joint Cooperative Activity (JCA) from 21 to 25 Septembe

## P31 · singapore · production

Minister for Defence Chan Chun Sing Agrees with German Federal Minister of Defence to Further Strengthen Defence Relationship

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/1oct26-nr/) · source-stated date `2026-10-01`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/1oct26-nr/`.

Body SHA-256: `9599fb1f8f9b2e1c7373c0b30cdb3b08e31fd988799f96ce1a790faa44b03bdf` (2152 characters).

Existing desk labels: none recorded.

- Propose `defense_diplomacy` [E1]: Ministerial bilateral engagement.

- Propose `cyber_information` [E2]: Explicit cybersecurity cooperation.

- Propose `defense_industry` [E3]: Explicit defense-industrial cooperation.

- Propose `critical_minerals_supply_chains` [E4]: Supply-chain resilience discussed in defense cooperation; no claim of minerals content.

E1 · `text_original[16:149]` (Unicode characters, end exclusive):

> inister for Defence Chan Chun Sing called on German Federal Minister of Defence Boris Pistorius this afternoon. Minister for Defence 

E2 · `text_original[697:810]` (Unicode characters, end exclusive):

> reas of mutual interest, including cybersecurity, countering hybrid threats, defence industry, supply chain resil

E3 · `text_original[739:855]` (Unicode characters, end exclusive):

> curity, countering hybrid threats, defence industry, supply chain resilience and upholding international law. Minist

E4 · `text_original[757:880]` (Unicode characters, end exclusive):

>  hybrid threats, defence industry, supply chain resilience and upholding international law. Minister Chan welcomed Germany'

Review question/limitation: Several named cooperation areas in one sentence: review materiality rather than automatically tagging every listed agenda item.

## P32 · singapore · production

Media Reply on 1SG N M Pranesh

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/28sep26-mq/) · source-stated date `2026-09-28`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/28sep26-mq/`.

Body SHA-256: `575f17e48623c6a2436115be9f238878740874bfe064cbf7a81625e535ae8340` (504 characters).

Existing desk labels: none recorded.

Unclassified: Personnel conviction and discharge are not covered by v1.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 28 September 2026 The Singapore Armed Forces (SAF) holds its service personnel to high standards of discipline and integrity. Serv

## P33 · singapore · production

Speech by Minister of State for Defence Desmond Choo at the 27th Asia-Pacific Programme for Senior Military Officers (APPSMO) on 28 September 2026 at Grand Copthorne Waterfront Hotel

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/28sep26-speech/) · source-stated date `2026-09-28`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/28sep26-speech/`.

Body SHA-256: `84379abcaf0963b82bad2e4bd326bf2403714c6c886090e8c550334846ad8a24` (11399 characters).

Existing desk labels: none recorded.

- Propose `doctrine_strategy` [E1]: Speech substantively considers future force-employment concepts.

- Propose `emerging_technology` [E2]: Technological changes to military affairs.

- Propose `cyber_information` [E3]: Cyberspace capability discussed as part of military affairs.

- Propose `economic_security` [E4]: Explicit economic/national-security linkage.

- Propose `critical_minerals_supply_chains` [E5]: Defense-relevant supply chains are explicitly linked to military power.

E1 · `text_original[1693:1815]` (Unicode characters, end exclusive):

>  such as drones are changing their concepts of operations. This includes rapid developments in AI and cyberspace. Larger a

E2 · `text_original[1753:1870]` (Unicode characters, end exclusive):

> his includes rapid developments in AI and cyberspace. Larger and more sophisticated militaries must increasingly expe

E3 · `text_original[1753:1870]` (Unicode characters, end exclusive):

> his includes rapid developments in AI and cyberspace. Larger and more sophisticated militaries must increasingly expe

E4 · `text_original[2059:2227]` (Unicode characters, end exclusive):

> plement conventional capabilities. Economic security has also become inseparable from national security. Military power depends not only on the capabilities a country p

E5 · `text_original[2259:2390]` (Unicode characters, end exclusive):

> rial capacity, infrastructure, and supply chains that sustain them. These developments have understandably prompted us to think and

Review question/limitation: Broad strategic speech discusses many technologies; reviewer must check materiality thresholds for each proposed label.

## P34 · singapore · production

Speech by Coordinating Minister for Public Services and Minister for Defence Chan Chun Sing at St Luke’s Hospital’s 30th Anniversary Gala Dinner on 25 September 2026 at Shangri-La Singapore

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/25sep26-speech/) · source-stated date `2026-09-25`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/25sep26-speech/`.

Body SHA-256: `ad52c164d3ffd8831027f435fd3a283ce02528de00394dcf6dfd936d04c42e6b` (6040 characters).

Existing desk labels: none recorded.

Unclassified: Hospital anniversary and aging/social services lack a substantive defense-security subject.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 25 September 2026 Good evening, everyone. Congratulations to all for your 30th anniversary, 30 years of service. Tonight, the real

## P35 · singapore · production

Largest ASEAN Defence Ministers’ Meeting (ADMM)-Plus Exercise in a Decade with the Participation of 2,200 Personnel from 19 Countries

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/22sep26-nr/) · source-stated date `2026-09-22`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/22sep26-nr/`.

Body SHA-256: `10866200805dcb0d67974d98e34e12400c4dfd179ffdfb5bcd3408d493f21177` (4165 characters).

Existing desk labels: none recorded.

- Propose `military_exercises` [E1]: Named multinational disaster-response exercise.

- Propose `alliances_partnerships` [E2]: Institutional regional defense cooperation mechanism.

E1 · `text_original[133:257]` (Unicode characters, end exclusive):

> lian agencies are participating in Exercise Trident Resolve (XTR), held in Banten, Indonesia from 20 to 26 September 2026. P

E2 · `text_original[1139:1248]` (Unicode characters, end exclusive):

> 6 September 2026. XTR is the first ADMM-Plus Combined Field Training Exercise (FTX) involving three Experts’ 

Review question/limitation: ADMM-Plus framework supports partnership topic; disaster response remains only indirectly represented.

## P36 · singapore · production

Infographic: Ex Trident Resolve 2026

[Source](https://www.mindef.gov.sg/news-and-events/latest-releases/22sep26-infographic/) · source-stated date `2026-09-22`

Record identity: `singapore` / `sg_mindef_releases` / exact source URL above.

Pinned store: `4efa9c086f70ae3fe4d24720754f323c8e393ebf:pla_watch.db`; `articles.url` = `https://www.mindef.gov.sg/news-and-events/latest-releases/22sep26-infographic/`.

Body SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (0 characters).

Existing desk labels: none recorded.

Unclassified: Image-only record has no captured body; title-only classification withheld.

## P37 · japan · shadow

日米合同委員会合意について

[Source](https://www.mod.go.jp/j/press/news/2026/10/05b.pdf) · source-stated date `2026-10-05`

Record identity: `japan` / `jp_mod_news_ja` / exact source URL above.

Pinned store: `e362cbc6b16633d80d3c4425468526ffde3dad21:state/shadow.db`; `shadow_records.url` = `https://www.mod.go.jp/j/press/news/2026/10/05b.pdf`.

Body SHA-256: `d8ec17263a4465f75f79e03d2096ce82b9094da649d2ee0d7f198778d0cd0eb8` (580 characters).

Existing desk labels: none recorded.

- Propose `force_posture_basing` [E1]: Limited use of a named airfield facility.

- Propose `military_exercises` [E2]: Named exercise for which access is authorized.

- Propose `alliances_partnerships` [E3]: Formal bilateral access framework is central.

E1 · `text_original[32:136]` (Unicode characters, end exclusive):

> について 日米合同委員会において、ＦＡＣ５１２１築城飛行場の追加財産の限定使用 について合意しましたのでお知らせします。 なお、合意概要については別添のとおりです。 日米合同委員会合意事案概要 件 名 ＦＡＣ

E2 · `text_original[309:418]` (Unicode characters, end exclusive):

> 帯 施 設： － 【事案内容】 本件は、日米共同統合演習（実動演習）「キーン・ソード２７」及び航空機訓練 移転（ＡＴＲ）に係る共同訓練を実施するため、標記施設の一部を日米地位協定第 ２条第４項（ｂ）に基づき限定使用する

E3 · `text_original[357:463]` (Unicode characters, end exclusive):

> 空機訓練 移転（ＡＴＲ）に係る共同訓練を実施するため、標記施設の一部を日米地位協定第 ２条第４項（ｂ）に基づき限定使用することについて、日米合同委員会の承認を得 たものである。 記 土 地：約 29,000 ㎡ 

## P38 · japan · shadow

令和８年熊本地震復旧に係る対応

[Source](https://www.mod.go.jp/j/press/news/2026/08/28a.pdf) · source-stated date `2026-08-28`

Record identity: `japan` / `jp_mod_news_ja` / exact source URL above.

Pinned store: `e362cbc6b16633d80d3c4425468526ffde3dad21:state/shadow.db`; `shadow_records.url` = `https://www.mod.go.jp/j/press/news/2026/08/28a.pdf`.

Body SHA-256: `92c3546b6ef898a2bccadcf297e640a8f3fe60a94252673b73c5b5708486a068` (232 characters).

Existing desk labels: none recorded.

Unclassified: Disaster-response support spending has no clear v1 fit.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> ○ 人件費（災害派遣等手当、航海手当、航空作業手当） 約１．３億円 ○ 民間船舶の運営費 約３．２億円 令和８年熊本地震復旧に係る対応 令和８年 ８ 月 防衛省 （注）これらの施策の実施に当たっては、既定経費の活用も検討 〇「はくおうⅡ」による入浴等支援 災害

Review question/limitation: Military disaster-relief expenditure is not clearly procurement or security-economic policy. No v1 topic fits the central subject.

## P39 · japan · shadow

日米合同委員会合意について

[Source](https://www.mod.go.jp/j/press/news/2026/08/28b.pdf) · source-stated date `2026-08-28`

Record identity: `japan` / `jp_mod_news_ja` / exact source URL above.

Pinned store: `e362cbc6b16633d80d3c4425468526ffde3dad21:state/shadow.db`; `shadow_records.url` = `https://www.mod.go.jp/j/press/news/2026/08/28b.pdf`.

Body SHA-256: `383bf4256d8de47e529f3f766226dadd9c175c993bb0efd20f45c27423867d77` (929 characters).

Existing desk labels: none recorded.

- Propose `force_posture_basing` [E1]: Named-airfield property-use authorization.

- Propose `military_exercises` [E2]: Named joint exercise.

- Propose `alliances_partnerships` [E3]: Formal bilateral access framework.

E1 · `text_original[132:236]` (Unicode characters, end exclusive):

> 合同委員会合意事案概要 件 名 ＦＡＣ３１９３浜松飛行場における財産の限定使用について 承 認 年 月 日 令和８年８月１８日 施設・区域名称 ＦＡＣ３１９３浜松飛行場 合意対象所在地 静岡県浜松市 合意対象

E2 · `text_original[310:421]` (Unicode characters, end exclusive):

> 。） 附 帯 施 設： － 【事案内容】 □□本件は、日米韓共同訓練（フリーダム・エッジ２６）を実施するため、日米地位 協定第２条第４項（ｂ）の適用ある施設及び区域として、標記施設の一部を限定使 用することについて、日米合

E3 · `text_original[330:434]` (Unicode characters, end exclusive):

>  □□本件は、日米韓共同訓練（フリーダム・エッジ２６）を実施するため、日米地位 協定第２条第４項（ｂ）の適用ある施設及び区域として、標記施設の一部を限定使 用することについて、日米合同委員会の承認を得たもので

## P40 · japan · shadow

日米合同委員会合意について

[Source](https://www.mod.go.jp/j/press/news/2026/08/28f.pdf) · source-stated date `2026-08-28`

Record identity: `japan` / `jp_mod_news_ja` / exact source URL above.

Pinned store: `e362cbc6b16633d80d3c4425468526ffde3dad21:state/shadow.db`; `shadow_records.url` = `https://www.mod.go.jp/j/press/news/2026/08/28f.pdf`.

Body SHA-256: `82435e345942c5ec3345c1457c4ad4e9935cbf07096ec36f6c6536031362b627` (1403 characters).

Existing desk labels: none recorded.

- Propose `force_posture_basing` [E1]: Joint use of named facilities.

- Propose `military_exercises` [E2]: Named command-post exercise.

- Propose `alliances_partnerships` [E3]: Formal bilateral access framework.

E1 · `text_original[68:172]` (Unicode characters, end exclusive):

> 、ＦＡＣ６０４４キャ ンプ瑞慶覧及びＦＡＣ６０５６牧港補給地区の一部の共同使用についてほか２ 件について合意しましたのでお知らせします。 なお、合意概要については別添のとおりです。 日米合同委員会合意事案概要

E2 · `text_original[470:578]` (Unicode characters, end exclusive):

> 物： － 附帯施設： － 【事案内容】 本件は、日米豪共同指揮所演習「ヤマサクラ－９１」を実施するため、日米地位 協定第２条第４項（ａ）に基づき、標記施設の一部を共同使用することについて、 日米合同委員会の承認を得た

E3 · `text_original[487:591]` (Unicode characters, end exclusive):

> 容】 本件は、日米豪共同指揮所演習「ヤマサクラ－９１」を実施するため、日米地位 協定第２条第４項（ａ）に基づき、標記施設の一部を共同使用することについて、 日米合同委員会の承認を得たものである。 記 （１）Ｆ

## P41 · japan · shadow

日米合同委員会合意について

[Source](https://www.mod.go.jp/j/press/news/2026/08/27b.pdf) · source-stated date `2026-08-27`

Record identity: `japan` / `jp_mod_news_ja` / exact source URL above.

Pinned store: `e362cbc6b16633d80d3c4425468526ffde3dad21:state/shadow.db`; `shadow_records.url` = `https://www.mod.go.jp/j/press/news/2026/08/27b.pdf`.

Body SHA-256: `fd4eaf5138625f63dc3ec14f6c71bbc25de1b2676b597d487edad3a4a5c59120` (3609 characters).

Existing desk labels: none recorded.

- Propose `force_posture_basing` [E1]: Facility development at a named airfield.

- Propose `alliances_partnerships` [E2]: Bilateral committee authorizes named military facility plans.

E1 · `text_original[36:142]` (Unicode characters, end exclusive):

> 合意について 日米合同委員会において、ＦＡＣ２００１三沢飛行場における誘導路の設置 に係る施設整備計画についてほか９件について合意しましたのでお知らせしま す。 なお、合意概要については別添のとおりです。 日米合

E2 · `text_original[0:101]` (Unicode characters, end exclusive):

> （お知らせ） 令和 8 年 8 月 27 日 防 衛 省 日米合同委員会合意について 日米合同委員会において、ＦＡＣ２００１三沢飛行場における誘導路の設置 に係る施設整備計画についてほか９件について合意

## P42 · vietnam · shadow

Hợp tác đào tạo, nghiên cứu công nghệ an ninh với Đại học Concordia, Canada

[Source](https://bocongan.gov.vn/bai-viet/cu-the-hoa-hop-tac-dao-tao-nghien-cuu-cong-nghe-an-ninh-voi-dai-hoc-concordia-1791199677) · source-stated date `2026-10-05`

Record identity: `vietnam` / `vn_mps_foreign_affairs_vi` / exact source URL above.

Pinned store: `46f6a0e59e25b03868bf7ad600963d6921ee5124:state/shadow.db`; `shadow_records.url` = `https://bocongan.gov.vn/bai-viet/cu-the-hoa-hop-tac-dao-tao-nghien-cuu-cong-nghe-an-ninh-voi-dai-hoc-concordia-1791199677`.

Body SHA-256: `d7c22a5ed0d6d6b6b1dba03df20bab1d6352d80d75adcdba6853b68d23fdc1d2` (1870 characters).

Existing desk labels: none recorded.

- Propose `cyber_information` [E1]: Security-linked cybersecurity research cooperation.

- Propose `emerging_technology` [E2]: Security-linked AI research is substantive.

E1 · `text_original[755:867]` (Unicode characters, end exclusive):

> c Concordia trong các lĩnh vực AI, an ninh mạng, quản trị dữ liệu và công nghệ số, đồng thời khẳng định đây là n

E2 · `text_original[751:867]` (Unicode characters, end exclusive):

> i học Concordia trong các lĩnh vực AI, an ninh mạng, quản trị dữ liệu và công nghệ số, đồng thời khẳng định đây là n

Review question/limitation: Public-security AI/cyber cooperation fits security technologies; defense_diplomacy would incorrectly imply a military institution.

## P43 · vietnam · shadow

Mở rộng hợp tác công nghệ, công nghiệp an ninh với các đối tác Thổ Nhĩ Kỳ

[Source](https://bocongan.gov.vn/bai-viet/mo-rong-hop-tac-cong-nghe-cong-nghiep-an-ninh-voi-cac-doi-tac-tho-nhi-ky-1791199100) · source-stated date `2026-10-05`

Record identity: `vietnam` / `vn_mps_foreign_affairs_vi` / exact source URL above.

Pinned store: `46f6a0e59e25b03868bf7ad600963d6921ee5124:state/shadow.db`; `shadow_records.url` = `https://bocongan.gov.vn/bai-viet/mo-rong-hop-tac-cong-nghe-cong-nghiep-an-ninh-voi-cac-doi-tac-tho-nhi-ky-1791199100`.

Body SHA-256: `a74afdee76e0937e514d7551fdaae618ac91b5ca95ab291c51cd6c789f0277f9` (3513 characters).

Existing desk labels: none recorded.

- Propose `emerging_technology` [E1]: AI applications in public-security cooperation.

E1 · `text_original[3035:3146]` (Unicode characters, end exclusive):

>  cơ sở giam giữ, tích hợp dữ liệu, ứng dụng AI và các giải pháp ứng phó với những thách thức an ninh mới.
> Bộ tr

Review question/limitation: Police security industry is not defense_industry by default. Propose AI only; security-industry coverage is a possible gap.

## P44 · vietnam · shadow

Việt Nam và Myanmar chú trọng hợp tác đấu tranh với các loại tội phạm mới

[Source](https://bocongan.gov.vn/bai-viet/viet-nam-va-myanmar-chu-trong-hop-tac-dau-tranh-voi-cac-loai-toi-pham-moi-1790933646) · source-stated date `2026-10-02`

Record identity: `vietnam` / `vn_mps_foreign_affairs_vi` / exact source URL above.

Pinned store: `46f6a0e59e25b03868bf7ad600963d6921ee5124:state/shadow.db`; `shadow_records.url` = `https://bocongan.gov.vn/bai-viet/viet-nam-va-myanmar-chu-trong-hop-tac-dau-tranh-voi-cac-loai-toi-pham-moi-1790933646`.

Body SHA-256: `420a79b902de06951c8cd7108e297e8fa48c3bac028d007cca9ad886cf0b38d0` (5076 characters).

Existing desk labels: none recorded.

Unclassified: Police cooperation cannot be relabeled as military diplomacy.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> Chiều 02/10/2026, tại Hà Nội, Thượng tướng Lê Văn Tuyến, Ủy viên Trung ương Đảng, Thứ trưởng Bộ Công an đã có buổi làm việc với Th

Review question/limitation: International police/crime cooperation is not automatically defense diplomacy. Hold unclassified pending security-cooperation scope review.

## P45 · vietnam · shadow

Bộ Công Thương lấy ý kiến Dự thảo Nghị định về kinh doanh xăng dầu

[Source](https://moit.gov.vn/tin-tuc/bo-cong-thuong-lay-y-kien-du-thao-nghi-dinh-ve-kinh-doanh-xang-dau.html) · source-stated date `2026-09-30`

Record identity: `vietnam` / `vn_moit_energy_vi` / exact source URL above.

Pinned store: `aac24cb4c2bc7e63da80df5212954d48cf492945:state/shadow.db`; `shadow_records.url` = `https://moit.gov.vn/tin-tuc/bo-cong-thuong-lay-y-kien-du-thao-nghi-dinh-ve-kinh-doanh-xang-dau.html`.

Body SHA-256: `e6f9d70b9536324cc36160e984f6f1a1746d210fe595ea559658a0b129268266` (7521 characters).

Existing desk labels: none recorded.

- Propose `economic_security` [E1]: Petroleum-market regulation explicitly linked to energy security.

E1 · `text_original[1396:1514]` (Unicode characters, end exclusive):

> hời liên quan chặt chẽ đến bảo đảm an ninh năng lượng, cung ứng xăng dầu và ổn định kinh tế vĩ mô. Tinh thần xuyên suố

Review question/limitation: Explicit energy-security phrase supports economic_security; ordinary fuel policy alone would not.

## P46 · vietnam · shadow

Chính phủ ban hành Nghị quyết về việc kéo dài thời hạn áp dụng ưu đãi thuế xăng dầu đến hết năm 2026

[Source](https://moit.gov.vn/tin-tuc/chinh-phu-ban-hanh-nghi-quyet-ve-viec-keo-dai-thoi-han-ap-dung-uu-dai-thue-xang-dau-den-het-nam-2026.html) · source-stated date `2026-09-30`

Record identity: `vietnam` / `vn_moit_energy_vi` / exact source URL above.

Pinned store: `aac24cb4c2bc7e63da80df5212954d48cf492945:state/shadow.db`; `shadow_records.url` = `https://moit.gov.vn/tin-tuc/chinh-phu-ban-hanh-nghi-quyet-ve-viec-keo-dai-thoi-han-ap-dung-uu-dai-thue-xang-dau-den-het-nam-2026.html`.

Body SHA-256: `6e7ca7a61de495b1710490ebf517c748d14df4728b6b12f3d2c11d0354456717` (2108 characters).

Existing desk labels: none recorded.

- Propose `economic_security` [E1]: Tax policy explicitly linked to energy security; no sanctions claim.

E1 · `text_original[1497:1615]` (Unicode characters, end exclusive):

> át triển kinh tế - xã hội, đảm bảo an ninh năng lượng, ổn định thị trường xăng, dầu, Bộ Công Thương có ý kiến đề xuất 

Review question/limitation: Energy-security rationale supports economic_security, but broad tax measures do not constitute export_controls_sanctions.

## P47 · vietnam · shadow

Hội thảo khoa học quốc gia "Định hướng phát triển công nghiệp hỗ trợ Việt Nam"

[Source](https://moit.gov.vn/tin-tuc/hoi-thao-khoa-hoc-quoc-gia-dinh-huong-phat-trien-cong-nghiep-ho-tro-viet-nam-.html) · source-stated date `2026-09-30`

Record identity: `vietnam` / `vn_moit_foundational_industry_vi` / exact source URL above.

Pinned store: `5e414cf28cf99bb6ae8b64052f701ea27fcf19b7:state/shadow.db`; `shadow_records.url` = `https://moit.gov.vn/tin-tuc/hoi-thao-khoa-hoc-quoc-gia-dinh-huong-phat-trien-cong-nghiep-ho-tro-viet-nam-.html`.

Body SHA-256: `f32cd4760f744620dca3a2278c79c89a5d246d8bb682f47e3e30af4fb0c7fe59` (9577 characters).

Existing desk labels: none recorded.

- Propose `economic_security` [E1]: Supporting-industry policy explicitly linked to economic security and strategic autonomy.

- Propose `critical_minerals_supply_chains` [E2]: Industrial resilience and strategic autonomy; minerals are not asserted.

E1 · `text_original[5745:5860]` (Unicode characters, end exclusive):

>  đồng thời là vấn đề liên quan đến an ninh kinh tế, tự chủ chiến lược và mục tiêu đưa Việt Nam trở thành nước phát 

E2 · `text_original[2948:3065]` (Unicode characters, end exclusive):

> ích then chốt, quyết định năng lực tự chủ chiến lược, khả năng cạnh tranh quốc gia.
> Đồng chí Nguyễn Thanh Nghị - Ủy v

Review question/limitation: Generic supporting industry has explicit strategic-autonomy rationale; review whether supply-chain topic is too broad. No defense-sector assumption.

## P48 · philippines · shadow

AFP Chief Calls for One Visayas Command Under New Commander

[Source](https://www.afp.mil.ph/news/afp-chief-calls-for-one-visayas-command-under-new-commander) · source-stated date `2026-10-06`

Record identity: `philippines` / `ph_afp_articles` / exact source URL above.

Pinned store: `492001f34ba6176169b6acc96a237f05592a3395:state/shadow.db`; `shadow_records.url` = `https://www.afp.mil.ph/news/afp-chief-calls-for-one-visayas-command-under-new-commander`.

Body SHA-256: `197500c043dab7e88e673243dc4050a4f62f0f8a22abf6212a03032a5d7e20c0` (1481 characters).

Existing desk labels: none recorded.

Unclassified: Command appointment and unity exhortation do not by themselves establish basing/posture changes.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> CAMP AGUINALDO, Quezon City -- The Armed Forces of the Philippines (AFP) welcomed Major General Moises Micor PAF as the new Comman

## P49 · philippines · shadow

AFP Chief Recognizes Naval Personnel, Underscores Maritime Readiness

[Source](https://www.afp.mil.ph/news/afp-chief-recognizes-naval-personnel-underscores-maritime-readiness) · source-stated date `2026-10-06`

Record identity: `philippines` / `ph_afp_articles` / exact source URL above.

Pinned store: `492001f34ba6176169b6acc96a237f05592a3395:state/shadow.db`; `shadow_records.url` = `https://www.afp.mil.ph/news/afp-chief-recognizes-naval-personnel-underscores-maritime-readiness`.

Body SHA-256: `a1ac7efd29b9e66a3c2868cb5d593c53f69e96b9e09fac1d4b809f9dc26eaf02` (1325 characters).

Existing desk labels: none recorded.

- Propose `maritime_security` [E1]: Naval maritime-security mission is substantively described.

E1 · `text_original[866:991]` (Unicode characters, end exclusive):

>  personnel in sustaining the AFP’s maritime security mission.
> 
> The visit reaffirmed the AFP’s commitment to maintaining a str

Review question/limitation: Awards surround substantive maritime-readiness content; topic rests on mission discussion, not naval affiliation.

## P50 · philippines · shadow

AFP Marks 36 Years of Code of Conduct, Honors Excellence in Service

[Source](https://www.afp.mil.ph/news/afp-marks-36-years-of-code-of-conduct-honors-excellence-in-service) · source-stated date `2026-10-05`

Record identity: `philippines` / `ph_afp_articles` / exact source URL above.

Pinned store: `492001f34ba6176169b6acc96a237f05592a3395:state/shadow.db`; `shadow_records.url` = `https://www.afp.mil.ph/news/afp-marks-36-years-of-code-of-conduct-honors-excellence-in-service`.

Body SHA-256: `e6c9986e9f5aca93774687a49bf0d9cfe98bc397b7ff334dd6656c199b63da47` (1291 characters).

Existing desk labels: none recorded.

Unclassified: Code-of-conduct ceremony and integrity awards lack a v1 subject fit.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> CAMP AGUINALDO, Quezon City - The Armed Forces of the Philippines (AFP) marked the 36th Year of the AFP Code of Conduct and recogn

## P51 · philippines · shadow

AFP, PNP, PCG Conclude Interagency Exercise “Pagsasanay Sanlakas” 2026

[Source](https://www.afp.mil.ph/news/afp-pnp-pcg-conclude-interagency-exercise-pagsasanay-sanlakas-2026) · source-stated date `2026-10-03`

Record identity: `philippines` / `ph_afp_articles` / exact source URL above.

Pinned store: `492001f34ba6176169b6acc96a237f05592a3395:state/shadow.db`; `shadow_records.url` = `https://www.afp.mil.ph/news/afp-pnp-pcg-conclude-interagency-exercise-pagsasanay-sanlakas-2026`.

Body SHA-256: `0f99d426c5860b25788a152f7a487463bf6979db84915b58c9509b5817dce003` (1382 characters).

Existing desk labels: none recorded.

- Propose `military_exercises` [E1]: Named interagency disaster-response training.

E1 · `text_original[126:246]` (Unicode characters, end exclusive):

> t Guard (PCG) concluded the second Interagency Exercise (IAX 02-2026), dubbed “Pagsasanay Sanlakas,” on October 2, 2026,

Review question/limitation: Coast-guard participation in earthquake response does not justify gray_zone_coast_guard.

## P52 · philippines · shadow

AFP, PNP, PCG Sustain Joint Readiness Through 2026 Inter-Agency Exercise

[Source](https://www.afp.mil.ph/news/afp-pnp-pcg-sustain-joint-readiness-through-2026-inter-agency-exercise) · source-stated date `2026-10-01`

Record identity: `philippines` / `ph_afp_articles` / exact source URL above.

Pinned store: `492001f34ba6176169b6acc96a237f05592a3395:state/shadow.db`; `shadow_records.url` = `https://www.afp.mil.ph/news/afp-pnp-pcg-sustain-joint-readiness-through-2026-inter-agency-exercise`.

Body SHA-256: `2207cc71ef080ebfecbf35dba117ce775b3583b043415b39352a65622d62f724` (1241 characters).

Existing desk labels: none recorded.

- Propose `military_exercises` [E1]: Named joint emergency-readiness exercise.

E1 · `text_original[147:273]` (Unicode characters, end exclusive):

> t Guard (PCG), formally opened the 2026 Inter-Agency Exercise during a ceremony held on September 30, here.
> 
> The opening cerem

## P53 · philippines · shadow

AFP Chief Visits Lumbia Air Base, Highlights Continuing Development

[Source](https://www.afp.mil.ph/news/afp-chief-visits-lumbia-air-base-highlights-continuing-development) · source-stated date `2026-09-27`

Record identity: `philippines` / `ph_afp_articles` / exact source URL above.

Pinned store: `492001f34ba6176169b6acc96a237f05592a3395:state/shadow.db`; `shadow_records.url` = `https://www.afp.mil.ph/news/afp-chief-visits-lumbia-air-base-highlights-continuing-development`.

Body SHA-256: `525c01e30c10b4d9066846b16079a9261b18492e759129b00be9f363217212be` (1158 characters).

Existing desk labels: none recorded.

- Propose `force_posture_basing` [E1]: Operational air-base development and unit relocation.

E1 · `text_original[251:377]` (Unicode characters, end exclusive):

> 
> General Nafarrete highlighted the relocation and integration of the 15th Strike Wing and the 590th Air Base Group, Philippine

## P54 · philippines · shadow

AFP Advances Leadership Continuity with Confirmation of 35 Senior Officers

[Source](https://www.afp.mil.ph/news/afp-advances-leadership-continuity-with-confirmation-of-35-senior-officers) · source-stated date `2026-09-25`

Record identity: `philippines` / `ph_afp_articles` / exact source URL above.

Pinned store: `492001f34ba6176169b6acc96a237f05592a3395:state/shadow.db`; `shadow_records.url` = `https://www.afp.mil.ph/news/afp-advances-leadership-continuity-with-confirmation-of-35-senior-officers`.

Body SHA-256: `0ee012b8f3c19a7ee58f041e3102aeca0dca0fa9fe1446726bee96126bc8ae4b` (859 characters).

Existing desk labels: none recorded.

Unclassified: Senior-officer confirmations are personnel/governance rather than regional subject topics.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> CAMP AGUINALDO, Quezon City - The Armed Forces of the Philippines (AFP) strengthened its senior leadership following the Commissio

## P55 · indonesia · shadow

Disaksikan Presiden, Menhan Hadiri Penyerahan Rp13,2 Triliun dan 259 Ribu Hektare Kawasan Hutan Kepada Negara

[Source](https://www.kemhan.go.id/2026/10/07/disaksikan-presiden-menhan-hadiri-penyerahan-rp132-triliun-dan-259-ribu-hektare-kawasan-hutan-kepada-negara.html) · source-stated date `2026-10-07`

Record identity: `indonesia` / `id_kemhan_news` / exact source URL above.

Pinned store: `dc6a76193d17f3513c32ec1de02902ed01421437:state/shadow.db`; `shadow_records.url` = `https://www.kemhan.go.id/2026/10/07/disaksikan-presiden-menhan-hadiri-penyerahan-rp132-triliun-dan-259-ribu-hektare-kawasan-hutan-kepada-negara.html`.

Body SHA-256: `1d645e81aa7d42e80ec6b2c94f4897893f5a861aa08a4cfa8a6d3d78916c0197` (2466 characters).

Existing desk labels: none recorded.

Unclassified: Forest restitution/fines ceremony attended by defense minister lacks an explicit security-policy nexus.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> Jakarta – Menteri Pertahanan RI Sjafrie Sjamsoeddin menghadiri acara Pemyerahan Denda Administratif Rp13,2 triliun dan Penguasaan 

## P56 · indonesia · shadow

Menhan Sjafrie Terima Courtesy Call Athan Singapura, Apresiasi Dedikasi Selama Bertugas

[Source](https://www.kemhan.go.id/2026/10/06/menhan-sjafrie-terima-courtesy-call-athan-singapura-apresiasi-dedikasi-selama-bertugas.html) · source-stated date `2026-10-06`

Record identity: `indonesia` / `id_kemhan_news` / exact source URL above.

Pinned store: `dc6a76193d17f3513c32ec1de02902ed01421437:state/shadow.db`; `shadow_records.url` = `https://www.kemhan.go.id/2026/10/06/menhan-sjafrie-terima-courtesy-call-athan-singapura-apresiasi-dedikasi-selama-bertugas.html`.

Body SHA-256: `f4bc6ef7beec542e21c238d4b2c0e4880a615266d22f096255f131bb7f5375d8` (1655 characters).

Existing desk labels: none recorded.

- Propose `defense_diplomacy` [E1]: Defense-attache engagement explicitly situated in defense diplomacy.

E1 · `text_original[253:373]` (Unicode characters, end exclusive):

> ut merupakan bagian dari rangkaian diplomasi pertahanan antara Indonesia dan Singapura, sekaligus menjadi momentum berak

## P57 · indonesia · shadow

Atas Nama Negara, Menhan Sjafrie Anugerahkan Satyalancana Dharma Samudera kepada Personel JMSDF yang Terlibat Penanganan Karhutla

[Source](https://www.kemhan.go.id/2026/09/30/atas-nama-negara-menhan-sjafrie-anugerahkan-satyalancana-dharma-samudera-kepada-personel-jmsdf-yang-terlibat-penanganan-karhutla.html) · source-stated date `2026-09-30`

Record identity: `indonesia` / `id_kemhan_news` / exact source URL above.

Pinned store: `dc6a76193d17f3513c32ec1de02902ed01421437:state/shadow.db`; `shadow_records.url` = `https://www.kemhan.go.id/2026/09/30/atas-nama-negara-menhan-sjafrie-anugerahkan-satyalancana-dharma-samudera-kepada-personel-jmsdf-yang-terlibat-penanganan-karhutla.html`.

Body SHA-256: `b1c3a242582abce3750908bb9649e05e3aafcae7d33dec59bdc7061deea1157f` (2845 characters).

Existing desk labels: none recorded.

- Propose `defense_diplomacy` [E1]: Official defense relationship recognition for military humanitarian assistance.

- Propose `alliances_partnerships` [E2]: Explicit defense cooperation agreement.

E1 · `text_original[1480:1598]` (Unicode characters, end exclusive):

> an wujud konkret dari implementasi hubungan bilateral serta Kerja Sama Pertahanan (Defense Cooperation Agreement/DCA) 

E2 · `text_original[1528:1661]` (Unicode characters, end exclusive):

> teral serta Kerja Sama Pertahanan (Defense Cooperation Agreement/DCA) antara Indonesia dan Jepang, baik yang sedang berjalan maupun d

Review question/limitation: Disaster relief is not training or maritime security merely because the platform is a ship; gap remains.

## P58 · korea · shadow

북한 탄도미사일 발사 관련 국방부 입장

[Source](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297) · source-stated date `2026-10-06`

Record identity: `korea` / `kr_policy_mnd_releases` / exact source URL above.

Pinned store: `c20b7eb826b34e208ce5dccb7ea3c5306693718a:state/shadow.db`; `shadow_records.url` = `https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297`.

Body SHA-256: `ef066346d991369fe99a1ad8db5dae85979c05c484d0f77462c25b30684b0284` (429 characters).

Existing desk labels: none recorded.

- Propose `alliances_partnerships` [E1]: Substantive bilateral combined-defense posture.

E1 · `text_original[115:229]` (Unicode characters, end exclusive):

> 후 미사일을 탐지·추적하고 발사 원점을 정확히 식별하였음.
> □ 한미는 확고한 연합방위태세를 유지하고 있으며, 북한이 최근 발사한 미사일은 한미가 보유한 방어자산으로 충분히 탐지·요격 가능한 수준으로 평가하

Review question/limitation: Ballistic missiles are not automatically nuclear. Korean Peninsula has no geographic topic; alliance label is only partial coverage.

## P59 · korea · shadow

국방부장관, 취임 후 첫 캠프 험프리스 방문

[Source](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784196) · source-stated date `2026-10-02`

Record identity: `korea` / `kr_policy_mnd_releases` / exact source URL above.

Pinned store: `c20b7eb826b34e208ce5dccb7ea3c5306693718a:state/shadow.db`; `shadow_records.url` = `https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784196`.

Body SHA-256: `bcf6c5e77f3f3e08005bdd2dee68740cc8fcf9576d6707031d2dd7bc0f0c7914` (657 characters).

Existing desk labels: none recorded.

- Propose `force_posture_basing` [E1]: Named military base and posture visit.

- Propose `defense_diplomacy` [E2]: Minister meets allied commands.

- Propose `alliances_partnerships` [E3]: Combined-defense cooperation is substantive.

E1 · `text_original[191:298]` (Unicode characters, end exclusive):

> 철 장관은 먼저 환영 의장행사에 참석하여 ‘한미동맹의 심장’인 험프리스 기지에서 헌신하고 있는 한미 장병들을 격려하였습니다.
> ◦ 강신철 장관은 전쟁의 역사를 통해 ‘함께 싸우겠다는 의지의 중요

E2 · `text_original[381:488]` (Unicode characters, end exclusive):

> Xavier T. Brunson) 한미연합사/주한미군사/유엔사 사령관을 접견하여 주요 현안에 대해 논의하였습니다.
> □ 또한, 강신철 장관은 한반도의 평화와 안정을 위해 헌신하고 있는 한미연합사

E3 · `text_original[58:163]` (Unicode characters, end exclusive):

> 리스 방문
> - 취임 후 첫 방문을 통해 굳건한 연합방위태세 및 한미 공조 재확인
> □ 강신철 국방부장관은 10월 2일(금) 오전, 취임 후 처음으로 캠프 험프리스를 방문하여 굳건한 연합방위태

## P60 · korea · shadow

국방부 유해발굴감식단, 6·25 전사자 귀환 주제 「국유단: 귀환작전」 피규어 전시

[Source](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156783602) · source-stated date `2026-09-30`

Record identity: `korea` / `kr_policy_mnd_releases` / exact source URL above.

Pinned store: `c20b7eb826b34e208ce5dccb7ea3c5306693718a:state/shadow.db`; `shadow_records.url` = `https://www.korea.kr/briefing/pressReleaseView.do?newsId=156783602`.

Body SHA-256: `e4aaf200e520b3f69b83583ba7f221759a11ea3b86b244d261c109a48d576165` (1420 characters).

Existing desk labels: none recorded.

Unclassified: War-dead remembrance exhibition is outside v1.

E1 · `text_original[0:130]` (Unicode characters, end exclusive):

> 보도 자료
> 보도시점
> 배포 이후
> 배포
> 2026.9.30.(수) 08:30
> 국방부 유해발굴감식단, 6·25 전사자 귀환 주제 「국유단: 귀환작전」 피규어 전시
> - 제78주년 국군의 날 맞아 10월 한 달 동안 12만 미수습 6·25 전사
