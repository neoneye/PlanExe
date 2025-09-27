# Luigi Pipeline Dependency Chain

1. StartTimeTask
   └── 2. SetupTask
       ├── 3. RedlineGateTask
       │   └── 4. PremiseAttackTask
       │       └── 5. IdentifyPurposeTask
       │           ├── 6. MakeAssumptionsTask
       │           │   └── 7. DistillAssumptionsTask
       │           │       └── 8. ReviewAssumptionsTask
       │           │           └── 9. IdentifyRisksTask
       │           │               ├── 57. RiskMatrixTask
       │           │               │   └── 58. RiskMitigationPlanTask
       │           │               └── (feeds into Governance & Report later)
       │           ├── 10. CurrencyStrategyTask
       │           └── 11. PhysicalLocationsTask
       │
       ├── 12. StrategicDecisionsMarkdownTask
       │   └── 13. ScenariosMarkdownTask
       │       └── 14. ExpertFinder
       │           └── 15. ExpertCriticism
       │               └── 16. ExpertOrchestrator
       │
       ├── 17. CreateWBSLevel1
       │   └── 18. CreateWBSLevel2
       │       └── 19. CreateWBSLevel3
       │           ├── 20. IdentifyWBSTaskDependencies
       │           ├── 21. EstimateWBSTaskDurations
       │           ├── 22. WBSPopulate
       │           ├── 23. WBSTaskTooltip
       │           └── (→ feeds into 24. WBSTask & 25. WBSProject)
       │               └── 26. ProjectSchedulePopulator
       │                   └── 27. ProjectSchedule
       │                       ├── 28. ExportGanttDHTMLX
       │                       ├── 29. ExportGanttCSV
       │                       └── 30. ExportGanttMermaid
       │
       ├── 31. FindTeamMembers
       │   ├── 32. EnrichTeamMembersWithContractType
       │   ├── 33. EnrichTeamMembersWithBackgroundStory
       │   ├── 34. EnrichTeamMembersWithEnvironmentInfo
       │   └── 35. TeamMarkdownDocumentBuilder
       │       └── 36. ReviewTeam
       │
       ├── 37. CreatePitch
       │   └── 38. ConvertPitchToMarkdown
       │
       ├── 39. ExecutiveSummary
       ├── 40. ReviewPlan
       ├── 41. ReportGenerator
       │
       ├── 42. GovernancePhase1AuditTask
       │   └── 43. GovernancePhase2InternalBodiesTask
       │       └── 44. GovernancePhase3ImplementationPlanTask
       │           └── 45. GovernancePhase4DecisionMatrixTask
       │               └── 46. GovernancePhase5MonitoringTask
       │                   └── 47. GovernancePhase6ExtraTask
       │                       └── 48. ConsolidateGovernanceTask
       │
       ├── 49. DataCollection
       ├── 50. ObtainOutputFiles
       ├── 51. PipelineEnvironment
       ├── 52. LLMExecutor
       │
       ├── 53. WBSJSONExporter
       ├── 54. WBSDotExporter
       ├── 55. WBSPNGExporter
       ├── 56. WBSPDFExporter
       │
       ├── 59. BudgetEstimationTask
       │   └── 60. CashflowProjectionTask
       │
       └── 61. FinalReportAssembler
           ├── merges Governance outputs
           ├── merges Risk outputs
           ├── merges WBS & Schedule exports
           ├── merges Team documents
           ├── merges Pitch & Executive Summary
           └── produces **Final Report**