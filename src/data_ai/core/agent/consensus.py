"""
DATA-AI Agent 共识机制

提供多 Agent 协作的共识达成机制，包括投票、加权决策、专家裁决等。
参考 Hermes 和 Trae 的多 Agent 架构设计。
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from ...utils.exceptions import AgentException
from ...utils.logging import get_logger

if TYPE_CHECKING:
    from ...sdk import ChatResponse

logger = get_logger(__name__)


class ConsensusStrategy(Enum):
    """
    共识策略

    定义达成共识的方式
    """

    VOTING = "voting"  # 简单投票：多数决定
    WEIGHTED = "weighted"  # 加权投票：根据权重决定
    EXPERT = "expert"  # 专家裁决：由专家最终决定
    UNANIMOUS = "unanimous"  # 一致同意：需要所有人同意
    RANKED = "ranked"  # 排名投票：按排名计分
    CONDORCET = "condorcet"  # 孔多塞投票：两两比较
    DELEGATED = "delegated"  # 委托投票：代理投票

    @classmethod
    def get_description(cls, strategy: ConsensusStrategy) -> str:
        """获取策略描述"""
        descriptions = {
            cls.VOTING: "简单多数投票，获得最多票数的选项获胜",
            cls.WEIGHTED: "加权投票，根据投票者的权重计算结果",
            cls.EXPERT: "专家裁决，由指定的专家做出最终决定",
            cls.UNANIMOUS: "一致同意，需要所有投票者都同意",
            cls.RANKED: "排名投票，投票者对选项排名，按得分决定",
            cls.CONDORCET: "孔多塞投票，选项两两比较，击败所有其他选项的获胜",
            cls.DELEGATED: "委托投票，投票者可以将投票权委托给他人",
        }
        return descriptions.get(strategy, "未知策略")


class VoteValue(Enum):
    """投票值"""

    YES = "yes"  # 同意
    NO = "no"  # 反对
    ABSTAIN = "abstain"  # 弃权
    VETO = "veto"  # 否决（一票否决权）


class ProposalStatus(Enum):
    """提案状态"""

    DRAFT = "draft"  # 草稿
    PROPOSED = "proposed"  # 已提出
    VOTING = "voting"  # 投票中
    ACCEPTED = "accepted"  # 已接受
    REJECTED = "rejected"  # 已拒绝
    WITHDRAWN = "withdrawn"  # 已撤回
    EXPIRED = "expired"  # 已过期


@dataclass
class Proposal:
    """
    提案

    表示一个需要达成共识的提案
    """

    proposal_id: str
    title: str
    description: str
    proposer_id: str
    options: list[str] = field(default_factory=list)  # 选项列表
    status: ProposalStatus = ProposalStatus.DRAFT
    strategy: ConsensusStrategy = ConsensusStrategy.VOTING
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    min_votes: int = 1  # 最少投票数
    required_majority: float = 0.5  # 需要的多数比例
    metadata: dict[str, Any] = field(default_factory=dict)
    result: str | None = None  # 最终结果
    result_details: dict[str, Any] | None = None

    def __post_init__(self):
        """初始化后处理"""
        if not self.proposal_id:
            self.proposal_id = str(uuid.uuid4())

        # 默认选项：同意/反对
        if not self.options:
            self.options = ["同意", "反对"]

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @property
    def is_active(self) -> bool:
        """是否处于活跃状态"""
        return self.status == ProposalStatus.VOTING and not self.is_expired

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "proposer_id": self.proposer_id,
            "options": self.options,
            "status": self.status.value,
            "strategy": self.strategy.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "min_votes": self.min_votes,
            "required_majority": self.required_majority,
            "metadata": self.metadata,
            "result": self.result,
            "result_details": self.result_details,
        }


@dataclass
class Vote:
    """
    投票

    表示单个投票者的投票
    """

    vote_id: str
    proposal_id: str
    voter_id: str
    choice: str  # 选择的选项
    weight: float = 1.0  # 投票权重
    reason: str | None = None  # 投票理由
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if not self.vote_id:
            self.vote_id = str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "vote_id": self.vote_id,
            "proposal_id": self.proposal_id,
            "voter_id": self.voter_id,
            "choice": self.choice,
            "weight": self.weight,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class VotingRecord:
    """
    投票记录

    记录一个提案的所有投票信息
    """

    proposal_id: str
    votes: dict[str, Vote] = field(default_factory=dict)  # voter_id -> Vote
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None

    def add_vote(self, vote: Vote) -> bool:
        """
        添加投票

        Args:
            vote: 投票

        Returns:
            是否成功添加
        """
        if vote.voter_id in self.votes:
            return False  # 已经投过票

        self.votes[vote.voter_id] = vote
        return True

    def update_vote(self, vote: Vote) -> bool:
        """
        更新投票（允许改票）

        Args:
            vote: 新投票

        Returns:
            是否成功更新
        """
        self.votes[vote.voter_id] = vote
        return True

    def get_vote(self, voter_id: str) -> Vote | None:
        """获取投票"""
        return self.votes.get(voter_id)

    def has_voted(self, voter_id: str) -> bool:
        """检查是否已投票"""
        return voter_id in self.votes

    def get_vote_count(self) -> int:
        """获取投票数量"""
        return len(self.votes)

    def get_results(self) -> dict[str, float]:
        """
        获取投票结果

        Returns:
            选项 -> 得分（加权票数）
        """
        results: dict[str, float] = defaultdict(float)

        for vote in self.votes.values():
            results[vote.choice] += vote.weight

        return dict(results)

    def get_winner(self) -> tuple[str, float] | None:
        """
        获取获胜选项

        Returns:
            (选项, 得分) 或 None
        """
        results = self.get_results()
        if not results:
            return None

        winner = max(results.items(), key=lambda x: x[1])
        return winner

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "proposal_id": self.proposal_id,
            "votes": {vid: v.to_dict() for vid, v in self.votes.items()},
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "vote_count": self.get_vote_count(),
            "results": self.get_results(),
        }


class ConsensusManager:
    """
    共识管理器

    管理提案、投票和共识达成的全过程
    """

    def __init__(
        self,
        name: str = "consensus_manager",
        default_strategy: ConsensusStrategy = ConsensusStrategy.VOTING,
        default_voting_period_seconds: float = 300.0,  # 5分钟
        default_min_votes: int = 1,
        default_required_majority: float = 0.5,
        voter_weights: dict[str, float] | None = None,
        experts: set[str] | None = None,
    ):
        """
        初始化共识管理器

        Args:
            name: 管理器名称
            default_strategy: 默认共识策略
            default_voting_period_seconds: 默认投票周期（秒）
            default_min_votes: 默认最少投票数
            default_required_majority: 默认需要的多数比例
            voter_weights: 投票者权重映射
            experts: 专家 ID 集合
        """
        self.name = name
        self.default_strategy = default_strategy
        self.default_voting_period_seconds = default_voting_period_seconds
        self.default_min_votes = default_min_votes
        self.default_required_majority = default_required_majority

        self.voter_weights = voter_weights or {}
        self.experts = experts or set()

        # 提案存储
        self._proposals: dict[str, Proposal] = {}
        # 投票记录
        self._voting_records: dict[str, VotingRecord] = {}
        # 已注册的投票者
        self._voters: set[str] = set()

        self.logger = get_logger(f"{__name__}.{name}")

    def register_voter(
        self,
        voter_id: str,
        weight: float = 1.0,
        is_expert: bool = False,
    ) -> None:
        """
        注册投票者

        Args:
            voter_id: 投票者 ID
            weight: 投票权重
            is_expert: 是否为专家
        """
        self._voters.add(voter_id)
        self.voter_weights[voter_id] = weight

        if is_expert:
            self.experts.add(voter_id)

        self.logger.debug(
            "投票者已注册",
            voter_id=voter_id,
            weight=weight,
            is_expert=is_expert,
        )

    def unregister_voter(self, voter_id: str) -> None:
        """
        注销投票者

        Args:
            voter_id: 投票者 ID
        """
        self._voters.discard(voter_id)
        self.voter_weights.pop(voter_id, None)
        self.experts.discard(voter_id)

    def propose(
        self,
        title: str,
        description: str,
        proposer_id: str,
        options: list[str] | None = None,
        strategy: ConsensusStrategy | None = None,
        voting_period_seconds: float | None = None,
        min_votes: int | None = None,
        required_majority: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Proposal:
        """
        提出提案

        Args:
            title: 提案标题
            description: 提案描述
            proposer_id: 提案者 ID
            options: 选项列表
            strategy: 共识策略
            voting_period_seconds: 投票周期
            min_votes: 最少投票数
            required_majority: 需要的多数比例
            metadata: 元数据

        Returns:
            创建的提案
        """
        proposal_id = str(uuid.uuid4())

        # 计算过期时间
        voting_period = voting_period_seconds or self.default_voting_period_seconds
        expires_at = None
        if voting_period > 0:
            from datetime import timedelta

            expires_at = datetime.now() + timedelta(seconds=voting_period)

        proposal = Proposal(
            proposal_id=proposal_id,
            title=title,
            description=description,
            proposer_id=proposer_id,
            options=options or ["同意", "反对"],
            status=ProposalStatus.PROPOSED,
            strategy=strategy or self.default_strategy,
            expires_at=expires_at,
            min_votes=min_votes or self.default_min_votes,
            required_majority=required_majority or self.default_required_majority,
            metadata=metadata or {},
        )

        self._proposals[proposal_id] = proposal

        self.logger.info(
            "提案已创建",
            proposal_id=proposal_id,
            title=title,
            proposer=proposer_id,
            strategy=proposal.strategy.value,
        )

        return proposal

    def start_voting(self, proposal_id: str) -> bool:
        """
        开始投票

        Args:
            proposal_id: 提案 ID

        Returns:
            是否成功开始
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False

        if proposal.status != ProposalStatus.PROPOSED:
            return False

        proposal.status = ProposalStatus.VOTING

        # 创建投票记录
        self._voting_records[proposal_id] = VotingRecord(proposal_id=proposal_id)

        self.logger.info("投票已开始", proposal_id=proposal_id)

        return True

    def vote(
        self,
        proposal_id: str,
        voter_id: str,
        choice: str,
        reason: str | None = None,
        weight: float | None = None,
    ) -> Vote | None:
        """
        投票

        Args:
            proposal_id: 提案 ID
            voter_id: 投票者 ID
            choice: 选择
            reason: 理由
            weight: 权重（None 使用注册权重）

        Returns:
            投票对象，失败返回 None
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            self.logger.warning("提案不存在", proposal_id=proposal_id)
            return None

        if proposal.status != ProposalStatus.VOTING:
            self.logger.warning("提案不在投票状态", proposal_id=proposal_id, status=proposal.status.value)
            return None

        if proposal.is_expired:
            self.logger.warning("提案已过期", proposal_id=proposal_id)
            return None

        # 验证选项
        if choice not in proposal.options:
            self.logger.warning("无效的选项", proposal_id=proposal_id, choice=choice, options=proposal.options)
            return None

        # 获取投票记录
        record = self._voting_records.get(proposal_id)
        if not record:
            return None

        # 计算权重
        vote_weight = weight if weight is not None else self.voter_weights.get(voter_id, 1.0)

        # 创建投票
        vote = Vote(
            vote_id=str(uuid.uuid4()),
            proposal_id=proposal_id,
            voter_id=voter_id,
            choice=choice,
            weight=vote_weight,
            reason=reason,
        )

        # 添加到记录
        if not record.add_vote(vote):
            self.logger.warning("已经投过票", proposal_id=proposal_id, voter_id=voter_id)
            return None

        self.logger.info(
            "投票成功",
            proposal_id=proposal_id,
            voter_id=voter_id,
            choice=choice,
            weight=vote_weight,
        )

        return vote

    def resolve(self, proposal_id: str) -> dict[str, Any] | None:
        """
        解决提案，计算最终结果

        Args:
            proposal_id: 提案 ID

        Returns:
            结果详情，失败返回 None
        """
        proposal = self._proposals.get(proposal_id)
        record = self._voting_records.get(proposal_id)

        if not proposal or not record:
            return None

        # 根据策略计算结果
        if proposal.strategy == ConsensusStrategy.VOTING:
            result = self._resolve_voting(proposal, record)
        elif proposal.strategy == ConsensusStrategy.WEIGHTED:
            result = self._resolve_weighted(proposal, record)
        elif proposal.strategy == ConsensusStrategy.EXPERT:
            result = self._resolve_expert(proposal, record)
        elif proposal.strategy == ConsensusStrategy.UNANIMOUS:
            result = self._resolve_unanimous(proposal, record)
        elif proposal.strategy == ConsensusStrategy.RANKED:
            result = self._resolve_ranked(proposal, record)
        else:
            result = self._resolve_voting(proposal, record)

        # 更新提案状态
        if result.get("resolved"):
            proposal.status = ProposalStatus.ACCEPTED if result.get("accepted") else ProposalStatus.REJECTED
            proposal.result = result.get("winner")
            proposal.result_details = result

        record.ended_at = datetime.now()

        self.logger.info(
            "提案已解决",
            proposal_id=proposal_id,
            status=proposal.status.value,
            result=proposal.result,
        )

        return result

    def _resolve_voting(
        self,
        proposal: Proposal,
        record: VotingRecord,
    ) -> dict[str, Any]:
        """
        简单投票解决

        多数决定
        """
        results = record.get_results()
        total_votes = sum(results.values())

        if total_votes < proposal.min_votes:
            return {
                "resolved": False,
                "reason": "投票数不足",
                "total_votes": total_votes,
                "min_votes": proposal.min_votes,
            }

        winner = record.get_winner()
        if not winner:
            return {
                "resolved": False,
                "reason": "无有效投票",
            }

        winner_option, winner_score = winner
        majority_ratio = winner_score / total_votes if total_votes > 0 else 0

        accepted = majority_ratio >= proposal.required_majority

        return {
            "resolved": True,
            "accepted": accepted,
            "winner": winner_option,
            "winner_score": winner_score,
            "total_votes": total_votes,
            "majority_ratio": majority_ratio,
            "required_majority": proposal.required_majority,
            "results": results,
        }

    def _resolve_weighted(
        self,
        proposal: Proposal,
        record: VotingRecord,
    ) -> dict[str, Any]:
        """
        加权投票解决

        根据投票者权重计算
        """
        # 加权投票已经在投票时处理了权重
        return self._resolve_voting(proposal, record)

    def _resolve_expert(
        self,
        proposal: Proposal,
        record: VotingRecord,
    ) -> dict[str, Any]:
        """
        专家裁决

        只计算专家的投票
        """
        expert_votes = {vid: vote for vid, vote in record.votes.items() if vid in self.experts}

        if not expert_votes:
            # 没有专家投票，回退到普通投票
            return self._resolve_voting(proposal, record)

        # 计算专家投票结果
        expert_results: dict[str, float] = defaultdict(float)
        for vote in expert_votes.values():
            expert_results[vote.choice] += vote.weight

        total_expert_votes = sum(expert_results.values())
        winner = max(expert_results.items(), key=lambda x: x[1]) if expert_results else None

        if not winner:
            return {
                "resolved": False,
                "reason": "无有效专家投票",
            }

        winner_option, winner_score = winner

        return {
            "resolved": True,
            "accepted": True,
            "winner": winner_option,
            "winner_score": winner_score,
            "total_expert_votes": total_expert_votes,
            "expert_results": dict(expert_results),
            "all_results": record.get_results(),
        }

    def _resolve_unanimous(
        self,
        proposal: Proposal,
        record: VotingRecord,
    ) -> dict[str, Any]:
        """
        一致同意解决

        需要所有投票者都选择同一选项
        """
        results = record.get_results()
        total_votes = sum(results.values())

        if total_votes < proposal.min_votes:
            return {
                "resolved": False,
                "reason": "投票数不足",
                "total_votes": total_votes,
                "min_votes": proposal.min_votes,
            }

        # 检查是否所有投票都相同
        choices = set(vote.choice for vote in record.votes.values())

        if len(choices) == 1:
            winner = list(choices)[0]
            return {
                "resolved": True,
                "accepted": True,
                "winner": winner,
                "unanimous": True,
                "total_votes": total_votes,
                "results": results,
            }
        else:
            return {
                "resolved": True,
                "accepted": False,
                "winner": None,
                "unanimous": False,
                "reason": "未能达成一致",
                "choices": list(choices),
                "total_votes": total_votes,
                "results": results,
            }

    def _resolve_ranked(
        self,
        proposal: Proposal,
        record: VotingRecord,
    ) -> dict[str, Any]:
        """
        排名投票解决

        按排名计分（简化实现）
        """
        # 简化实现：使用加权投票
        return self._resolve_weighted(proposal, record)

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        """获取提案"""
        return self._proposals.get(proposal_id)

    def get_voting_record(self, proposal_id: str) -> VotingRecord | None:
        """获取投票记录"""
        return self._voting_records.get(proposal_id)

    def get_active_proposals(self) -> list[Proposal]:
        """获取活跃提案"""
        return [p for p in self._proposals.values() if p.is_active]

    def get_proposals_by_status(self, status: ProposalStatus) -> list[Proposal]:
        """按状态获取提案"""
        return [p for p in self._proposals.values() if p.status == status]

    def withdraw_proposal(self, proposal_id: str, proposer_id: str) -> bool:
        """
        撤回提案

        Args:
            proposal_id: 提案 ID
            proposer_id: 提案者 ID

        Returns:
            是否成功撤回
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False

        if proposal.proposer_id != proposer_id:
            return False

        if proposal.status not in (ProposalStatus.DRAFT, ProposalStatus.PROPOSED):
            return False

        proposal.status = ProposalStatus.WITHDRAWN

        self.logger.info("提案已撤回", proposal_id=proposal_id)

        return True

    def expire_proposals(self) -> list[str]:
        """
        使过期提案失效

        Returns:
            过期的提案 ID 列表
        """
        expired_ids: list[str] = []

        for proposal in self._proposals.values():
            if proposal.is_expired and proposal.status == ProposalStatus.VOTING:
                proposal.status = ProposalStatus.EXPIRED
                expired_ids.append(proposal.proposal_id)

                self.logger.info("提案已过期", proposal_id=proposal.proposal_id)

        return expired_ids

    async def run_consensus(
        self,
        proposal: Proposal,
        voters: list[str],
        vote_collector: Callable[[str, str], Awaitable[str | None]] | None = None,
        timeout_seconds: float = 60.0,
    ) -> dict[str, Any]:
        """
        运行共识过程

        自动收集投票并解决提案

        Args:
            proposal: 提案
            voters: 投票者 ID 列表
            vote_collector: 投票收集函数 (proposal_id, voter_id) -> choice
            timeout_seconds: 超时时间

        Returns:
            共识结果
        """
        # 保存提案
        self._proposals[proposal.proposal_id] = proposal

        # 开始投票
        self.start_voting(proposal.proposal_id)

        # 收集投票
        if vote_collector:
            for voter_id in voters:
                try:
                    choice = await asyncio.wait_for(
                        vote_collector(proposal.proposal_id, voter_id),
                        timeout=timeout_seconds / len(voters) if voters else timeout_seconds,
                    )

                    if choice:
                        self.vote(proposal.proposal_id, voter_id, choice)

                except asyncio.TimeoutError:
                    self.logger.warning("投票超时", voter_id=voter_id)
                except Exception as e:
                    self.logger.error("投票失败", voter_id=voter_id, error=str(e))

        # 解决提案
        result = self.resolve(proposal.proposal_id)

        return result or {"resolved": False, "reason": "无法解决提案"}

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        total_proposals = len(self._proposals)

        return {
            "total_proposals": total_proposals,
            "by_status": {status.value: len(self.get_proposals_by_status(status)) for status in ProposalStatus},
            "total_voters": len(self._voters),
            "total_experts": len(self.experts),
            "active_proposals": len(self.get_active_proposals()),
        }

    def clear(self) -> None:
        """清空所有数据"""
        self._proposals.clear()
        self._voting_records.clear()


class ConsensusError(AgentException):
    """共识错误"""

    def __init__(
        self,
        message: str,
        proposal_id: str | None = None,
        voter_id: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.proposal_id = proposal_id
        self.voter_id = voter_id


# ─────────────────────────────────────────────────────────────────────
# ConsensusBuilder - 真正将多个 Agent 的回答合成为一个最终答案
# ─────────────────────────────────────────────────────────────────────


class ConsensusMethod(Enum):
    """共识合成方法"""

    MAJORITY_VOTE = "majority_vote"  # 多数投票
    LENGTH_BASED = "length_based"  # 长度优先
    LLM_SYNTHESIS = "llm_synthesis"  # LLM 合成
    CONCATENATION = "concatenation"  # 拼接
    SEMANTIC = "semantic"  # 语义聚合
    WEIGHTED = "weighted"  # 加权


class ConsensusStrategy:
    """轻量级共识策略（不依赖投票系统，直接对响应做合成）"""

    def synthesize(
        self,
        responses: list[ChatResponse],
        original_query: str | None = None,
    ) -> ChatResponse:
        """根据多个响应合成一个最终响应

        默认实现：调用 :class:`ConcatenationStrategy` 做拼接兜底。
        子类应覆盖此方法以提供更智能的合成（多数投票、LLM 合成等）。
        """
        return ConcatenationStrategy().synthesize(responses, original_query)


class ConcatenationStrategy(ConsensusStrategy):
    """默认兜底：直接把多个响应拼起来，附上来源标记。"""

    def synthesize(
        self,
        responses: list[ChatResponse],
        original_query: str | None = None,
    ) -> ChatResponse:
        from data_ai.core.llm.manager import ChatResponse

        if not responses:
            raise ConsensusError("没有可合成的响应")

        parts = []
        for i, r in enumerate(responses, 1):
            content = (r.content or "").strip()
            if not content:
                continue
            tag = f"[响应 {i}]"
            model_tag = f" (model={r.model})" if r.model else ""
            parts.append(f"{tag}{model_tag}\n{content}")

        merged = "\n\n---\n\n".join(parts) if parts else (responses[0].content or "")
        return ChatResponse(
            content=merged,
            model="consensus:concatenation",
            usage={"responses_merged": len(responses)},
            finish_reason="consensus",
        )


class MajorityVoteStrategy(ConsensusStrategy):
    """多数投票：把内容切成句子/段落，出现最多的胜出"""

    def synthesize(
        self,
        responses: list[ChatResponse],
        original_query: str | None = None,
    ) -> ChatResponse:
        from data_ai.core.llm.manager import ChatResponse

        if not responses:
            raise ConsensusError("没有可合成的响应")

        # 把每个响应切成句子
        sentence_count: dict[str, int] = {}
        for r in responses:
            for s in self._split_sentences(r.content):
                key = s.strip()
                if len(key) < 5:
                    continue
                sentence_count[key] = sentence_count.get(key, 0) + 1

        if not sentence_count:
            return self._longest_response(responses)

        # 按出现次数排序；次数相同时优先长度更长的
        sorted_sentences = sorted(
            sentence_count.items(),
            key=lambda x: (x[1], len(x[0])),
            reverse=True,
        )
        # 构造最终结果：把出现过的句子按出现顺序拼起来
        chosen = [s for s, _ in sorted_sentences if sentence_count[s] >= max(1, len(responses) // 2)]
        if not chosen:
            chosen = [sorted_sentences[0][0]]

        final_content = "。\n".join(chosen) if any("\u4e00" <= c <= "\u9fff" for c in chosen[0]) else "\n".join(chosen)
        return ChatResponse(
            content=final_content,
            model="consensus:majority_vote",
            usage={"responses_merged": len(responses), "sentences_kept": len(chosen)},
            finish_reason="consensus",
        )

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        import re

        parts = re.split(r"(?<=[。！？!?\n])\s*", text or "")
        return [p.strip() for p in parts if p and p.strip()]

    @staticmethod
    def _longest_response(responses: list[ChatResponse]) -> ChatResponse:
        from data_ai.core.llm.manager import ChatResponse

        best = max(responses, key=lambda r: len(r.content or ""))
        return ChatResponse(
            content=best.content or "",
            model="consensus:length_fallback",
            finish_reason="consensus",
        )


class LLMSynthesisStrategy(ConsensusStrategy):
    """LLM 合成：调用 LLM 总结多个回答"""

    def __init__(self, llm_manager: Any | None = None):
        self.llm_manager = llm_manager

    def synthesize(
        self,
        responses: list[ChatResponse],
        original_query: str | None = None,
    ) -> ChatResponse:
        from data_ai.core.llm.manager import ChatResponse

        if not responses:
            raise ConsensusError("没有可合成的响应")

        if self.llm_manager is None:
            # 没有 LLM，降级到拼接
            concat = "\n\n---\n\n".join(r.content or "" for r in responses)
            return ChatResponse(
                content=concat,
                model="consensus:concat_fallback",
                finish_reason="consensus",
            )

        return _synthesize_with_llm(self.llm_manager, responses, original_query)


def _synthesize_with_llm(
    llm_manager: Any,
    responses: list[ChatResponse],
    original_query: str | None = None,
) -> ChatResponse:
    """调用 LLM 合成多个回答"""
    import asyncio

    from data_ai.core.llm.manager import ChatMessage

    numbered = "\n\n".join(f"[回答 {i + 1}]\n{r.content or ''}" for i, r in enumerate(responses))
    user_msg = (
        f"原始问题: {original_query or '(无)'}\n\n"
        f"以下是来自不同 Agent 的回答，请综合为一个准确、完整且无冲突的最终答案。\n"
        f"如果回答之间有冲突，请明确指出并给出最合理的版本。\n\n"
        f"{numbered}\n\n"
        f"请直接给出综合后的最终答案，不需要解释你的合成过程。"
    )
    messages = [
        ChatMessage(
            role="system",
            content="你是一个综合多个专家意见的助手，输出简洁、可执行。",
        ),
        ChatMessage(role="user", content=user_msg),
    ]

    async def _call() -> Any:
        return await llm_manager.chat(messages=messages, temperature=0.2)

    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在事件循环中；不可阻塞 — 退化为同步协程不安全的方案
                # 实际项目中应改为 await build_consensus_async
                return _synthesize_with_llm_sync(llm_manager, responses, original_query)
            response = loop.run_until_complete(_call())
        except RuntimeError:
            response = asyncio.run(_call())
    except Exception as e:
        logger.warning(f"LLM 合成失败，降级到拼接: {e}")
        concat = "\n\n---\n\n".join(r.content or "" for r in responses)
        from data_ai.core.llm.manager import ChatResponse

        return ChatResponse(
            content=concat,
            model="consensus:concat_fallback",
            finish_reason="consensus",
            usage={"error": str(e)},
        )

    from data_ai.core.llm.manager import ChatResponse

    return ChatResponse(
        content=response.content or "",
        model=response.model,
        usage=response.usage,
        finish_reason="consensus",
    )


def _synthesize_with_llm_sync(
    llm_manager: Any,
    responses: list[ChatResponse],
    original_query: str | None = None,
) -> ChatResponse:
    """在已运行事件循环中无法直接 asyncio.run 时的回退：使用线程池"""
    import concurrent.futures

    from data_ai.core.llm.manager import ChatMessage, ChatResponse

    numbered = "\n\n".join(f"[回答 {i + 1}]\n{r.content or ''}" for i, r in enumerate(responses))
    user_msg = (
        f"原始问题: {original_query or '(无)'}\n\n以下是来自不同 Agent 的回答，请综合为一个最终答案。\n\n{numbered}"
    )
    messages = [
        ChatMessage(role="system", content="你是一个综合多个专家意见的助手。"),
        ChatMessage(role="user", content=user_msg),
    ]

    def _runner() -> Any:
        # 同步 LLM 客户端可能没有同步方法 → 在线程中跑
        try:
            coro = llm_manager.chat(messages=messages, temperature=0.2)
            if hasattr(coro, "__await__"):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
            return coro
        except Exception as e:  # pragma: no cover
            logger.warning(f"线程池 LLM 合成失败: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_runner)
        response = future.result(timeout=60)

    if response is None:
        concat = "\n\n---\n\n".join(r.content or "" for r in responses)
        return ChatResponse(content=concat, model="consensus:concat_fallback", finish_reason="consensus")

    return ChatResponse(
        content=response.content or "",
        model=response.model,
        usage=response.usage,
        finish_reason="consensus",
    )


class ConsensusBuilder:
    """
    共识构建器

    将多个 Agent 的回答合成为一个最终答案。
    支持的策略：
    - majority_vote: 多数投票（句子级）
    - length_based:  选择最长的响应
    - llm_synthesis:  使用 LLM 综合
    - concatenation:  直接拼接
    - semantic:      语义聚合（默认 LLM 合成）
    - weighted:      加权（按 usage 中 token 数加权平均，最长优先）
    """

    def __init__(
        self,
        method: ConsensusMethod | str = ConsensusMethod.LLM_SYNTHESIS,
        llm_manager: Any | None = None,
    ):
        if isinstance(method, str):
            try:
                method = ConsensusMethod(method)
            except ValueError:
                method = ConsensusMethod.LLM_SYNTHESIS
        self.method = method
        self.llm_manager = llm_manager
        self._strategy: ConsensusStrategy = self._build_strategy(method, llm_manager)

    def set_llm_manager(self, manager: Any) -> None:
        self.llm_manager = manager
        self._strategy = self._build_strategy(self.method, manager)

    @staticmethod
    def _build_strategy(method: ConsensusMethod, llm_manager: Any | None) -> ConsensusStrategy:
        if method == ConsensusMethod.MAJORITY_VOTE:
            return MajorityVoteStrategy()
        if method == ConsensusMethod.LLM_SYNTHESIS or method == ConsensusMethod.SEMANTIC:
            return LLMSynthesisStrategy(llm_manager)
        if method == ConsensusMethod.LENGTH_BASED or method == ConsensusMethod.WEIGHTED:
            return MajorityVoteStrategy()  # 这两种降级到 vote（自动取最一致）
        if method == ConsensusMethod.CONCATENATION:
            return ConcatenationStrategy()  # 显式走拼接策略
        return LLMSynthesisStrategy(llm_manager)

    def build_consensus(
        self,
        responses: list[ChatResponse],
        original_query: str | None = None,
    ) -> ChatResponse:
        """
        将多个 Agent 响应合成为一个最终响应。

        Args:
            responses: Agent 响应列表
            original_query: 原始查询（用于 LLM 综合时提供上下文）

        Returns:
            合成的 ChatResponse
        """
        from data_ai.core.llm.manager import ChatResponse

        if not responses:
            raise ConsensusError("responses 不能为空")

        if len(responses) == 1:
            return responses[0]

        # 过滤空内容
        non_empty = [r for r in responses if (r.content or "").strip()]
        if not non_empty:
            return ChatResponse(
                content="",
                model="consensus:empty",
                finish_reason="consensus",
            )

        try:
            return self._strategy.synthesize(non_empty, original_query)
        except Exception as e:
            logger.warning(f"共识合成失败，回退到拼接: {e}")
            return self._concat(non_empty)

    async def build_consensus_async(
        self,
        responses: list[ChatResponse],
        original_query: str | None = None,
    ) -> ChatResponse:
        """异步版本"""
        from data_ai.core.llm.manager import ChatResponse

        if not responses:
            raise ConsensusError("responses 不能为空")

        if len(responses) == 1:
            return responses[0]

        non_empty = [r for r in responses if (r.content or "").strip()]
        if not non_empty:
            return ChatResponse(content="", model="consensus:empty", finish_reason="consensus")

        if self.method in (ConsensusMethod.LLM_SYNTHESIS, ConsensusMethod.SEMANTIC) and self.llm_manager is not None:
            from data_ai.core.llm.manager import ChatMessage

            numbered = "\n\n".join(f"[回答 {i + 1}]\n{r.content or ''}" for i, r in enumerate(non_empty))
            user_msg = (
                f"原始问题: {original_query or '(无)'}\n\n"
                f"以下是来自不同 Agent 的回答，请综合为一个最终答案：\n\n"
                f"{numbered}"
            )
            try:
                response = await self.llm_manager.chat(
                    messages=[
                        ChatMessage(role="system", content="你是一个综合多个专家意见的助手。"),
                        ChatMessage(role="user", content=user_msg),
                    ],
                    temperature=0.2,
                )
                return ChatResponse(
                    content=response.content or "",
                    model=response.model,
                    usage=response.usage,
                    finish_reason="consensus",
                )
            except Exception as e:
                logger.warning(f"异步 LLM 合成失败: {e}")
                return self._concat(non_empty)
        elif self.method == ConsensusMethod.MAJORITY_VOTE:
            try:
                return self._strategy.synthesize(non_empty, original_query)
            except Exception:
                return self._concat(non_empty)
        else:
            return self._concat(non_empty)

    def _concat(self, responses: list[ChatResponse]) -> ChatResponse:
        from data_ai.core.llm.manager import ChatResponse

        content = "\n\n---\n\n".join(r.content or "" for r in responses)
        return ChatResponse(
            content=content,
            model="consensus:concat",
            usage={"responses_merged": len(responses)},
            finish_reason="consensus",
        )
